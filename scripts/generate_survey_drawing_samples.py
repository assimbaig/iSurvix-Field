"""Reproducible synthetic drawing example; never represents an actual surveyed site.

Run .local/venv/Scripts/python.exe scripts/generate_survey_drawing_samples.py
Existing revision files are never overwritten. Supply --output for a fresh destination.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from core.survey_drawings import build_geometry, render_outputs


def sample_input():
    source = [{'type':'synthetic measured record','id':'SYN-001','page':1,'label':'SYNTHETIC / NOT A REAL SITE'}]
    snapshot = {'id':'SYNTHETIC-ONLY','project':{'id':'synthetic','name':'SYNTHETIC TRAINING PROJECT'},'site_id':'SYNTHETIC-001','date':'2026-10-21','drawing_records':[
        {'sheet':'site_layout','kind':'boundary','points':[[0,0],[6,0],[6,4],[0,4]],'unit':'m','verification_status':'confirmed','measurement_basis':'site_measured','sources':source,'tag':'B-01'},
        {'sheet':'site_layout','kind':'equipment','equipment_type':'cabinet','tag':'CAB-01','x':1,'y':1,'width':.8,'height':1.2,'unit':'m','verification_status':'confirmed','measurement_basis':'site_measured','sources':source},
        {'sheet':'site_layout','kind':'dimension','points':[[0,0],[6,0]],'value':6,'unit':'m','verification_status':'confirmed','measurement_basis':'site_measured','sources':source,'tag':'Boundary length'},
    ]}
    findings=[
        {'field':'Site ID','value':'SYNTHETIC-001','status':'Reported','confidence':1.0,'sources':source},
        {'field':'Cabinet CAB-01','category':'equipment','value':'1 generic cabinet; manufacturer/model not verified','status':'Needs review','sources':source},
        {'field':'Antenna model','category':'antenna','value':'Label unreadable; no exact model assigned','status':'Missing','confidence':.2,'sources':source},
        {'field':'Grounding route','value':'Concealed route not evidenced; no connection drawn','status':'Missing','sources':source},
    ]
    return snapshot, findings


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'samples'/'drawings'/'synthetic-survey')
    args=parser.parse_args()
    snapshot,findings=sample_input()
    result=render_outputs(build_geometry(snapshot,findings),args.output,prepared_by='Synthetic example generator')
    print(json.dumps({'pdf':result['pdf'],'sheets':len(result['sheets']),'geometry_digest':result['geometry_digest']},indent=2))
