"""Ordinary OCR contract tests use fake constructors, never load native weights."""
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest.mock import Mock,patch
from django.test import SimpleTestCase
from PIL import Image
from . import local_evidence_tools as tools


class OfflineOCRTests(SimpleTestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[2]/'.local'/'ocr-tests'
        root.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.models=self.root/'rapidocr_onnxruntime'/'models';self.models.mkdir(parents=True)
        self.names={'det_model_path':'ch_PP-OCRv4_det_infer.onnx','cls_model_path':'ch_ppocr_mobile_v2.0_cls_infer.onnx','rec_model_path':'ch_PP-OCRv4_rec_infer.onnx'}
        self.distribution=SimpleNamespace(locate_file=lambda name:self.root/name,version='1.4.4')
        tools._ocr_engine.cache_clear();self.addCleanup(tools._ocr_engine.cache_clear)

    def weights(self):
        for name in self.names.values():(self.models/name).write_bytes(b'CONTROLLED-FIXTURE-NOT-A-NATIVE-MODEL')

    def test_missing_weights_fail_before_constructor_or_download_can_run(self):
        constructor=Mock(side_effect=AssertionError('A native constructor must not run without installed weights'))
        with patch('importlib.metadata.distribution',return_value=self.distribution),patch.dict('sys.modules',{'rapidocr_onnxruntime':SimpleNamespace(RapidOCR=constructor)}):
            with self.assertRaises(ImportError):tools._ocr_engine()
        constructor.assert_not_called()

    def test_explicit_preflighted_local_model_paths_and_cpu_bounds_are_passed(self):
        self.weights()
        engine=Mock();constructor=Mock(return_value=engine)
        with patch('importlib.metadata.distribution',return_value=self.distribution),patch.dict('sys.modules',{'rapidocr_onnxruntime':SimpleNamespace(RapidOCR=constructor)}):
            self.assertIs(tools._ocr_engine(),engine)
            self.assertIs(tools._ocr_engine(),engine)
        constructor.assert_called_once_with(**{key:str((self.models/name).resolve()) for key,name in self.names.items()},intra_op_num_threads=2,inter_op_num_threads=1)

    def test_missing_weights_are_reported_unavailable_without_exposing_paths(self):
        constructor=Mock(side_effect=AssertionError('No native calls'))
        with patch('importlib.metadata.distribution',return_value=self.distribution),patch.dict('sys.modules',{'rapidocr_onnxruntime':SimpleNamespace(RapidOCR=constructor)}):
            result=tools.extract_local_tools(Image.new('RGB',(120,80),'white'),qr_backend=lambda image:[])
        self.assertEqual(result['errors'],[{'tool':'ocr','code':'unavailable'}])
        self.assertEqual(result['ocr_lines'],[])
        self.assertNotIn(str(self.root),str(result))
        constructor.assert_not_called()

    def test_empty_model_file_is_unavailable_before_loading(self):
        self.weights();(self.models/self.names['rec_model_path']).write_bytes(b'')
        constructor=Mock()
        with patch('importlib.metadata.distribution',return_value=self.distribution),patch.dict('sys.modules',{'rapidocr_onnxruntime':SimpleNamespace(RapidOCR=constructor)}):
            with self.assertRaises(ImportError):tools._ocr_engine()
        constructor.assert_not_called()

    def test_local_ocr_helper_preserves_text_confidence_and_boxes_without_qr(self):
        from .local_evidence_tools import local_ocr
        image=Image.new('RGB',(120,80),'white')
        rows=[[[[1,2],[50,2],[50,20],[1,20]],'SITE TEST-001',0.98]]
        with patch('core.local_evidence_tools._ocr_engine',side_effect=AssertionError('Controlled backend must not instantiate native OCR')):
            result=local_ocr(image,ocr_backend=lambda pixels:rows)
        self.assertEqual(result['ocr_lines'][0],{'text':'SITE TEST-001','confidence':0.98,'box':[[1.0,2.0],[50.0,2.0],[50.0,20.0],[1.0,20.0]]})
        self.assertEqual(result['qr_values'],[])
        self.assertEqual(result['errors'],[])

    def test_missing_package_metadata_is_unavailable_without_native_import(self):
        constructor=Mock()
        with patch('importlib.metadata.distribution',side_effect=metadata.PackageNotFoundError('rapidocr-onnxruntime')),patch.dict('sys.modules',{'rapidocr_onnxruntime':SimpleNamespace(RapidOCR=constructor)}):
            with self.assertRaises(ImportError):tools._ocr_engine()
        constructor.assert_not_called()

    def test_local_ocr_exposes_explicit_unavailable_and_unverified_provenance(self):
        from .local_evidence_tools import local_ocr
        def unavailable(image):raise ImportError('private filesystem path must stay private')
        result=local_ocr(Image.new('RGB',(120,80),'white'),ocr_backend=unavailable)
        self.assertEqual(result['status'],'unavailable')
        self.assertEqual(result['provenance']['engine'],'provided_adapter')
        self.assertEqual(result['provenance']['verification_status'],'unverified_source_text')
        self.assertNotIn('private filesystem',str(result))

    def test_qr_url_is_data_and_never_fetched(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('No QR network lookup')) as fetch:
            result=tools.extract_local_tools(Image.new('RGB',(120,80),'white'),ocr_backend=lambda image:[],qr_backend=lambda image:['https://example.invalid/private-path'])
        self.assertEqual(result['qr_values'],['https://example.invalid/private-path'])
        fetch.assert_not_called()
