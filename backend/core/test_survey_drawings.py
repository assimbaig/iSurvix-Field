"""Pure export tests: no database or real site/photo data are used."""
import copy
import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import ezdxf
import pymupdf
from PIL import Image

from .survey_drawings import build_geometry, render_outputs, validate_geometry, _digest


def working_directory():
    folder=Path(__file__).resolve().parents[2]/'.local'/'drawing-tests'
    folder.mkdir(parents=True,exist_ok=True)
    return TemporaryDirectory(dir=folder)


class SurveyDrawingTests(TestCase):
    def snapshot(self):
        return {'id':99,'project':{'id':7,'name':'Synthetic test project'},'site_id':'SYNTHETIC-ONLY','date':'2026-10-21'}

    def sourced(self, **kwargs):
        return {'sources':[{'type':'synthetic document','id':12,'page':2,'crop':'test-crop'}],**kwargs}

    def record(self, **kwargs):
        return self.sourced(kind='equipment',sheet='site_layout',x=0,y=0,width=1000,height=2000,unit='mm',verification_status='confirmed',measurement_basis='site_measured',tag='CAB-01',equipment_type='cabinet',**kwargs)

    def test_no_findings_produce_register_not_fabricated_equipment(self):
        result=build_geometry(self.snapshot(),[])
        self.assertEqual([s['key'] for s in result['sheets']],['register'])
        self.assertEqual(len(result['missing_information']),10)
        self.assertFalse(any(e['layer']=='EQUIPMENT' for s in result['sheets'] for e in s['entities']))
        self.assertIn('No structural/electrical design',str(result))

    def test_missing_measurement_is_explicit_in_geometry_pdf_and_dxf(self):
        geometry=build_geometry(self.snapshot(),[self.sourced(field='Tower height',value=None,unit='m',
            status='Missing',verification_status='needs_review')])
        sheet=next(s for s in geometry['sheets'] if s['key']=='tower_elevation')
        self.assertEqual(sheet['findings'][0]['answer'],'Not recorded | Missing')
        with working_directory() as temp:
            result=render_outputs(geometry,Path(temp))
            with pymupdf.open(result['pdf']) as document:
                text=' '.join(page.get_text() for page in document)
                self.assertIn('Not recorded | Missing',text)
                self.assertNotIn('m | needs_review',text)
            drawing=ezdxf.readfile(next(s['dxf'] for s in result['sheets'] if s['number']==sheet['number']))
            labels=[e.dxf.text for e in drawing.modelspace().query('TEXT')]
            self.assertIn('Not recorded | Missing',labels)

    def test_measured_scale_labels_align_with_separate_bar_endpoints(self):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        snapshot=self.snapshot();snapshot['drawing_records']=[self.record()]
        geometry=build_geometry(snapshot,[])
        sheet=next(s for s in geometry['sheets'] if s['key']=='site_layout')
        bar=next(e for e in sheet['entities'] if e.get('points')==[[24,88],[74,88]])
        labels=[e for e in sheet['entities'] if e['kind']=='text' and e['layer']=='DIMENSIONS']
        origin=next(e for e in labels if e['text']=='0')
        end=next(e for e in labels if e['text'].endswith(' mm'))
        self.assertEqual(origin['x'],bar['points'][0][0])
        self.assertAlmostEqual(end['x']+stringWidth(end['text'],'Helvetica',end['height']),bar['points'][1][0],places=3)
        self.assertLess(end['y']+end['height'],86)

    def test_unconfirmed_measurement_or_concealed_connection_never_drawn(self):
        data=self.snapshot();rec=self.record();rec['verification_status']='Needs review'
        connection=self.sourced(kind='connection',sheet='grounding',points=[[0,0],[1000,1000]],unit='mm',verification_status='confirmed',measurement_basis='recorded')
        data['drawing_records']=[rec,connection]
        result=build_geometry(data,[])
        self.assertEqual(len(result['warnings']),2)
        self.assertFalse(any(e['layer'] in ('MEASURED','EQUIPMENT','ROUTES') for s in result['sheets'] for e in s['entities']))

    def test_conflicting_dimensions_do_not_select_an_authoritative_value(self):
        data=self.snapshot();data['drawing_records']=[self.sourced(kind='dimension',points=[[0,0],[1000,0]],value=2000,unit='mm',verification_status='confirmed',measurement_basis='recorded')]
        result=build_geometry(data,[self.sourced(field='Tower height',value='22 m / 24 m',conflict=True)])
        self.assertTrue(any('conflicting' in w for w in result['warnings']))
        self.assertIn('CONFLICT',str(result))
        self.assertFalse(any(e['layer']=='DIMENSIONS' for s in result['sheets'] for e in s['entities']))

    def test_sourced_confirmed_coordinates_make_scaled_generic_envelopes(self):
        data=self.snapshot();data['drawing_records']=[self.record()]
        result=build_geometry(data,[])
        sheet=next(s for s in result['sheets'] if s['key']=='site_layout')
        self.assertIn('1:',sheet['scale'])
        entities=[e for e in sheet['entities'] if e['layer']=='EQUIPMENT']
        self.assertTrue(entities)
        self.assertTrue(all(e['sources'] for e in entities))
        self.assertIn('Typical - verify against site',str(sheet))
        validate_geometry(result)

    def test_extreme_geometry_and_invalid_units_fail_closed(self):
        for val in (float('nan'),float('inf'),1e12):
            data=self.snapshot();rec=self.record();rec['width']=val;data['drawing_records']=[rec]
            result=build_geometry(data,[])
            self.assertTrue(result['warnings'])
        result=build_geometry(self.snapshot(),[self.sourced(field='Model',value='ABC '*5000)])
        validate_geometry(result)

    def test_dxf_and_pdf_share_all_final_entities_and_digest(self):
        data=self.snapshot();data['drawing_records']=[self.record()]
        geometry=build_geometry(data,[self.sourced(field='Cabinet model',value='unverified',status='Needs review')])
        with working_directory() as temp:
            result=render_outputs(geometry,Path(temp),prepared_by='Engineer test')
            final=json.loads(Path(result['geometry']).read_text())
            digest=final.pop('digest');self.assertEqual(digest,_digest(final));self.assertEqual(digest,result['geometry_digest'])
            with pymupdf.open(result['pdf']) as pdf:
                self.assertEqual(len(pdf),len(final['sheets']))
                self.assertIn(digest,pdf.metadata['subject'])
                for index,sheet in enumerate(final['sheets']):
                    drawing=ezdxf.readfile(result['sheets'][index]['dxf'])
                    self.assertFalse(drawing.audit().has_errors)
                    entities=list(drawing.modelspace())
                    self.assertEqual(len(entities),len(sheet['entities']))
                    if sheet['key']=='site_layout':
                        inserts=list(drawing.modelspace().query('INSERT'))
                        self.assertTrue(inserts)
                        self.assertTrue(inserts[0].dxf.name.startswith('ISURVIX_CABINET_'))
                    for source,drawn in zip(sheet['entities'],entities):
                        tags=drawn.get_xdata('ISURVIX')
                        self.assertEqual(tags[1].value,_digest(source))
                    self.assertIn('DRAFT - FOR REVIEW',pdf[index].get_text())
                    self.assertTrue(Path(result['sheets'][index]['preview']).exists())
            self.assertNotIn('released',geometry)

    def test_previous_revisions_never_overwritten_and_release_requires_humans(self):
        geometry=build_geometry(self.snapshot(),[])
        with working_directory() as temp:
            first=render_outputs(geometry,Path(temp));original=Path(first['pdf']).read_bytes()
            with self.assertRaises(FileExistsError):render_outputs(geometry,Path(temp))
            second=render_outputs(geometry,Path(temp),revision=2)
            self.assertNotEqual(first['pdf'],second['pdf'])
            self.assertEqual(original,Path(first['pdf']).read_bytes())
            with self.assertRaises(ValueError):render_outputs(geometry,Path(temp),revision=3,released=True)
            released=render_outputs(geometry,Path(temp),revision=3,released=True,checked_by='QA user 2',approved_by='Lead user 3')
            with pymupdf.open(released['pdf']) as document:
                self.assertIn('RELEASED',document[0].get_text());self.assertNotIn('DRAFT - FOR REVIEW',document[0].get_text())

    def test_project_branding_not_hardcoded_or_shared_between_projects(self):
        geometry=build_geometry(self.snapshot(),[])
        with working_directory() as temp:
            folder=Path(temp);logo=folder/'logo.png';Image.new('RGB',(100,30),'blue').save(logo)
            with self.assertRaises(ValueError):render_outputs(geometry,folder/'wrong',branding={'project_id':8,'company_logo':str(logo)})
            result=render_outputs(geometry,folder/'right',branding={'project_id':7,'company_logo':str(logo),'client_logo':str(logo),'partner_logo':str(logo)})
            self.assertEqual(len(result['assets']),3)
            with zipfile.ZipFile(result['bundle']) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertIn('assets/company-logo.png',bundle.namelist())
                self.assertIn('assets/client-logo.png',bundle.namelist())
                self.assertIn('assets/partner-logo.png',bundle.namelist())
                self.assertIn('sv-001.dxf',bundle.namelist())
                extracted=folder/'extracted';bundle.extractall(extracted)
                exported=ezdxf.readfile(extracted/'sv-001.dxf')
                definitions=list(exported.objects.query('IMAGEDEF'))
                self.assertEqual(len(definitions),3)
                for definition in definitions:
                    self.assertTrue((extracted/definition.dxf.filename).is_file())
            final=json.loads(Path(result['geometry']).read_text())
            self.assertEqual(len([e for e in final['sheets'][0]['entities'] if e['kind']=='image']),3)
            self.assertNotIn('Nokia',str(final));self.assertNotIn('TAWAL',str(final))

    def test_findings_never_promoted_to_exact_measured_geometry(self):
        geometry=build_geometry(self.snapshot(),[self.sourced(field='Tower height',value=30,unit='m',confidence=.99,status='Confirmed from evidence')])
        sheet=next(s for s in geometry['sheets'] if s['key']=='tower_elevation')
        self.assertEqual(sheet['scale'],'Not to Scale')
        self.assertFalse(any(e['layer']=='MEASURED' for e in sheet['entities']))
        self.assertIn('30 m',str(sheet));self.assertIn('test-crop',str(geometry['sources']))

    def test_entity_limits_and_readable_bounds(self):
        findings=[self.sourced(field=f'Equipment {i}',value='Needs a detailed source verification') for i in range(490)]
        geometry=build_geometry(self.snapshot(),findings)
        self.assertLessEqual(len(geometry['sheets']),32)
        validate_geometry(geometry)
        self.assertTrue(any('page bound' in warning for warning in geometry['warnings']))
        invalid=copy.deepcopy(geometry);invalid['sheets'][0]['entities'].append({'kind':'text','x':410,'y':100,'height':4,'text':'Out of bounds','layer':'TEXT'})
        with self.assertRaises(ValueError):validate_geometry(invalid)

    def test_failed_export_publishes_no_partial_revision_and_retry_can_succeed(self):
        geometry=build_geometry(self.snapshot(),[])
        with working_directory() as temp:
            with patch('core.survey_drawings._pdf',side_effect=RuntimeError('Synthetic renderer interruption')):
                with self.assertRaises(RuntimeError):render_outputs(geometry,Path(temp))
            self.assertEqual(list(Path(temp).iterdir()),[])
            result=render_outputs(geometry,Path(temp))
            self.assertTrue(Path(result['pdf']).is_file())

    def test_processing_evidence_schema_keeps_component_source_and_page_reference(self):
        finding={'field_hint':'antenna_model','category':'equipment','component':'Sector A antenna','value':'UNKNOWN','basis':'visible','confidence':'low','source_id':'document:7:page:3','source_type':'pdf_page','reference':'PDF page 3, targeted crop 1','verification_status':'needs_review'}
        geometry=build_geometry(self.snapshot(),[finding])
        sheet=next(s for s in geometry['sheets'] if s['key']=='antenna_arrangement')
        self.assertEqual(sheet['findings'][0]['label'],'Sector A antenna')
        self.assertEqual(sheet['findings'][0]['sources'][0]['reference'],'PDF page 3, targeted crop 1')
        self.assertEqual(sheet['findings'][0]['sources'][0]['source_id'],'document:7:page:3')
        self.assertIn('needs_review',sheet['findings'][0]['answer'])
