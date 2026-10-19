"""Editable technical starter catalogs; never a jurisdictional compliance certificate."""
from copy import deepcopy
from .template_service import default_definition

ROOM_TYPES = ('bedroom','bathroom','walk_in_closet','staircase','prayer_room','pantry','kitchen','living','dining','majlis','laundry','study','office','balcony','terrace','garage','store','utility','plant','maid','guest','entrance','corridor','other')
LEGACY_STAGES = ('preconstruction','design','grey_structure','mep','finishing','external_works','testing_handover')
STRUCTURAL_STAGES = ('excavation','engineering_fill','field_density_test','lean_concrete','foundation_reinforcement','foundation_concrete','plinth_beams','ground_slab','lintel_beams','first_floor_reinforcement','first_floor_concrete','other_floor_reinforcement','other_floor_concrete')
STAGES = ('preconstruction','design','grey_structure',*STRUCTURAL_STAGES,'mep','finishing','external_works','testing_handover')
STAGE_LABELS={'engineering_fill':'Engineering fill and compaction','field_density_test':'Field density testing (FDT)','grey_structure':'Grey Structure coordination','other_floor_reinforcement':'Other floor reinforcement cycle','other_floor_concrete':'Other floor concrete cycle'}
MAX_ROOMS = 40
SOURCES = [
    {'title':'OSHA communication towers: safety topic coverage','url':'https://www.osha.gov/communication-towers'},
    {'title':'GOV.UK Approved Documents: building topic coverage','url':'https://www.gov.uk/government/collections/approved-documents'},
]
NOTICE = 'Editable baseline requiring project technical qualification. Use the approved project drawings, specifications, inspection method and applicable local requirements. Topic sources do not establish jurisdiction, acceptance thresholds or compliance. Record actual observations, document references, dated test results and human measurements with units; do not infer hidden work or measurements from photos.'

BTS = [
 ('design','Design and authorization','Approved site layout and drawing revisions|Structural design and geotechnical references|Equipment loading and foundation design coordination|Permits, access and land boundaries|Inspection and test plan hold points'),
 ('civil','Civil works and foundations','Site setting out and benchmark records|Excavation and ground condition records|Reinforcement and embedded items before concealment|Concrete placement, curing and test records|Foundation geometry and as-built measurements|Backfill, grading and drainage|Plinths, trenches and duct routes|Access road, compound fence and gates'),
 ('tower','Tower installation','Tower member identification and assembly|Member condition, deformation and protective coating|Connections and traceable bolt tightening records|Tower alignment and survey records|Base plates, anchor bolts and grout|Working platforms and handrails|Access ladder, fall protection and rescue arrangements|Cable support and obstruction clearance'),
 ('electrical','Power and earthing','Supply design and authorized connection records|Distribution boards, protection and circuit identification|Cable routing, support and terminations|Earthing electrodes, bonds and test records|Lightning protection and surge protection|Battery installation, ventilation and test records|Rectifier and standby power commissioning|Isolation, warning labels and safe access'),
 ('rf','RF and transmission','Antenna identity and approved mounting position|Antenna orientation, tilt and measured survey records|Radio units and mounting security|Feeder and fiber routing, bend control and labels|Weather sealing and connector workmanship|Equipment bonding and separation|Transmission link alignment and test records|RF exposure assessment and access controls'),
 ('safety','Safety and environmental controls','Work planning, competence and permit records|Fall prevention and rescue plan|Lifting and falling-object controls|Weather and site access restrictions|Electrical isolation and energized work controls|Fire protection, housekeeping and emergency access|Waste handling and environmental closeout'),
 ('commissioning','Commissioning and handover','Equipment inventory and serial-number records|Power-up and functional test records|Alarm, monitoring and backup-power tests|RF and transmission acceptance test records|Open defects and independent retest evidence|As-built drawings and operation manuals|Customer handover records and training references'),
]
COLOCATION = [
 ('baseline','Existing site baseline','Existing asset inventory and condition record|Pre-work photo and defect baseline|Existing operator interfaces and ownership|Approved scope and retained equipment boundaries|Live-service protection and access arrangements'),
 ('capacity','Capacity and design review','Approved structural capacity assessment|Proposed loads and mounting interfaces|Available power and protection coordination|Earthing and lightning system integration|Space, cable-route and maintainability review|RF coexistence and exposure assessment|Design changes and authorized revisions'),
 ('shared','Shared infrastructure works','Shared tower member and connection condition|Mounting works and protective coating repairs|Shared cable supports and segregated routes|Shared power interfaces and labeling|Bonding interfaces and test records|Shelter cooling and ventilation impact|Access, fire and emergency route continuity'),
 ('installation','New and modified equipment','New radio and antenna identity and mounting|Orientation and tilt survey records|Fiber, feeder and transmission interfaces|Power terminations and isolation labels|Weather sealing and workmanship|Equipment configuration and inventory changes'),
 ('cutover','Pre-cutover and cutover','Approved method, outage window and rollback plan|Pre-cutover baseline performance records|Operator authorization and communication log|Isolation and live-service protection checks|Cutover sequence and timestamped results|Post-cutover service and alarm tests|Rollback or incident record where applicable'),
 ('decommission','Decommissioning and restoration','Authorized redundant asset list|Safe isolation and removal records|Retained asset protection during removal|Removal inventory and owner disposition|Abandoned cable and penetration treatment|Site restoration and waste documentation'),
 ('handover','Modernization handover','Before and after asset reconciliation|Post-work structural and electrical test records|Updated drawings and operator interface records|Defects, corrective work and retest evidence|Service acceptance and handover references'),
]
CONSTRUCTION = [
 ('preconstruction','Preconstruction','Approved scope, permits and site boundaries|Survey benchmarks and existing condition records|Geotechnical and utility investigation references|Temporary works, access and protection plans|Inspection plan, hold points and material approvals|Existing services and neighbor protection'),
 ('design','Design','Approved architectural drawing coordination|Structural design and geotechnical coordination|MEP coordinated drawings and interface review|Fire strategy and emergency access design references|Accessibility and circulation design references|Moisture, thermal, acoustic and ventilation details|Design revisions and technical approvals'),
 ('grey_structure','Grey Structure','Setting out and levels survey records|Excavation, formation and ground condition|Foundation reinforcement and embedded services|Concrete placement, curing and test records|Columns, beams and structural connections|Slabs, openings and edge details|Masonry alignment and movement details|Roof structure and drainage falls|Concealed works inspection records'),
 ('mep','MEP','Water supply routing, supports and pressure tests|Drainage gradients, access and leak tests|Electrical containment, circuits and protective devices|Earthing, bonding and electrical test records|HVAC installation, ventilation and balancing records|Fire detection and suppression interfaces|Controls, communications and equipment identification|Service penetrations, sealing and maintenance access'),
 ('finishing','Finishing','Substrate preparation and surface condition|Waterproofing installation and test records|Wall and ceiling finish workmanship|Floor finish alignment, transitions and measured falls|Doors, windows, glazing and hardware|Joinery, fixtures and equipment installation|Sealants and weather-tightness details|Protection, cleaning and finish defects'),
 ('external_works','External works','External levels and surface water drainage|Paths, ramps, steps and edge protection|Boundary walls, gates and site access|External utilities and inspection chambers|Landscape, irrigation and reinstatement|External lighting and equipment interfaces'),
 ('testing_handover','Testing and handover','Commissioning plans and traceable test results|Life safety system integrated test records|Functional checks and maintenance access|Defects, corrective actions and independent retests|As-built drawings, manuals and warranties|Training and handover acceptance references'),
]


# Measurements and acceptance criteria remain project-specific human records.
STRUCTURAL_ACTIVITIES = [
 ('excavation','Excavation','Approved excavation limits, setting out and formation levels|Existing services identification and protection|Excavation support, access and water management|Exposed ground condition and geotechnical review|Formation inspection and authorization before covering','general'),
 ('engineering_fill','Engineering fill and compaction','Approved fill source, grading and material references|Preparation and acceptance of underlying formation|Layer location, identification and actual thickness records|Moisture conditioning and compaction method records|Plant access and adjacent structure protection|Layer inspection and authorization before next lift','density'),
 ('field_density_test','Field density testing (FDT)','Approved test method and laboratory competence references|Test location, layer and sample traceability|Moisture and density measurements with units|Reference laboratory compaction curve and approved criteria|Actual results compared by responsible reviewer|Nonconforming layer correction and independent retest','density'),
 ('lean_concrete','Lean concrete','Accepted formation and approved concrete reference|Level markers, extent and actual thickness records|Material delivery, mix reference and placement conditions|Placement workmanship and surface condition|Curing, protection and inspection before reinforcement','concrete'),
 ('foundation_reinforcement','Foundation reinforcement','Approved foundation reinforcement drawing and revision|Bar identity, grade and traceable material records|Bar arrangement, spacing, laps and anchorage measurements|Cover supports, chairs and reinforcement stability|Formwork geometry, cleanliness and access|Embedded items, earthing and service interfaces|Pre-pour hold point inspection and authorization','reinforcement'),
 ('foundation_concrete','Foundation concrete placement','Approved pour plan, mix and pre-pour authorization|Delivery batch and placement location traceability|Fresh concrete sampling, slump and site test records|Placement sequence, compaction and construction joints|Specimen identification and laboratory test references|Curing, protection and temperature records where specified|Post-placement condition, defects and repair authorization','concrete'),
 ('plinth_beams','Plinth beams','Approved plinth beam reinforcement and geometry|Formwork alignment, support and measured dimensions|Reinforcement, laps, cover and embedded interfaces|Pre-pour authorization and concrete batch traceability|Slump, specimens and placement records|Curing, protection and post-pour condition','concrete'),
 ('ground_slab','Ground slab','Approved slab details and accepted underlying layers|Fill compaction, service and concealed work records|Membrane, insulation and penetration interfaces|Reinforcement, cover, joints and level markers|Pre-pour approval and concrete delivery records|Slump, specimen and placement test records|Finishing, curing, measured levels and defect record','concrete'),
 ('lintel_beams','Lintel beams','Approved opening schedule and lintel design reference|Bearing, support and actual opening dimensions|Reinforcement, cover and embedded interface checks|Formwork stability and pre-pour authorization|Concrete delivery, site tests and specimen records|Curing, support removal authorization and condition','concrete'),
 ('first_floor_reinforcement','First floor reinforcement and formwork','Approved first floor structural drawings and revisions|Temporary support design, installation and inspection|Beam, slab and column reinforcement traceability|Reinforcement spacing, anchorage, laps and cover|Openings, edge details and embedded service coordination|Surveyed levels and pre-pour hold point authorization','reinforcement'),
 ('first_floor_concrete','First floor concrete placement','First floor pre-pour authorization and pour sequence|Delivery batch, pour zone and timing traceability|Slump and other specified site test records|Placement, compaction, joints and specimen identification|Curing and temporary load restrictions|Strength report references and support removal authorization|Post-pour survey, surface condition and defect records','concrete'),
 ('other_floor_reinforcement','Other floor reinforcement cycle - replicate per floor','Explicit floor, zone and approved drawing identification|Floor-specific temporary supports and survey records|Floor-specific reinforcement traceability and measurements|Openings, edge details and embedded service interfaces|Pre-pour inspection and authorization for identified floor','reinforcement'),
 ('other_floor_concrete','Other floor concrete cycle - replicate per floor','Explicit floor, pour zone and pre-pour approval|Batch, site tests and specimen traceability for floor|Placement, compaction and joint records|Curing, strength reports and support removal authorization|Floor-specific survey, defects and corrective retests','concrete'),
]
REGISTER_COLUMNS = {
 'general': [('location','Location / zone / floor'),('item','Inspection or test / sample ID'),('date','Date / time'),('method','Approved inspection / test method'),('criteria','Approved drawing / criteria reference'),('measured','Actual observations / measurements'),('units','Units'),('report','Report / survey reference'),('laboratory','Laboratory / responsible party'),('decision','Human decision: pass / fail / pending / N/A'),('reviewer','Reviewer / authorization reference'),('retest','Correction / retest reference')],
 'density': [('layer','Layer / lift ID'),('location','Test location / zone / floor'),('sample','Test / sample ID'),('date','Test date / time'),('method','Approved test method'),('criteria','Approved acceptance criteria reference'),('material','Fill material / source reference'),('thickness','Measured layer thickness / units'),('moisture','Measured moisture / units'),('wet_density','Measured wet density / units'),('dry_density','Measured dry density / units'),('reference_density','Reference maximum dry density / units'),('compaction','Calculated compaction result / units'),('report','FDT / laboratory report reference'),('laboratory','Laboratory / tester'),('decision','Human decision: pass / fail / pending / N/A'),('reviewer','Reviewer / authorization reference'),('retest','Correction / retest reference')],
 'concrete': [('location','Pour location / floor / element'),('batch','Batch / delivery ticket / mix reference'),('date','Placement date'),('times','Batch / arrival / test / placement times'),('method','Approved site test method'),('criteria','Approved mix / specification criteria reference'),('slump','Measured slump value'),('units','Slump units'),('site_tests','Other site tests / temperature values and units'),('specimens','Specimen IDs / sampling record'),('placement','Placement / compaction / curing record'),('laboratory','Laboratory / tester'),('lab_result','Laboratory age / strength result / units'),('report','Site / laboratory report reference'),('decision','Human decision: pass / fail / pending / N/A'),('reviewer','Reviewer / authorization reference'),('retest','Correction / retest reference')],
 'reinforcement': [('location','Floor / element / zone'),('drawing','Approved drawing / revision'),('material','Bar / material certificate reference'),('sample','Inspection / sample ID'),('date','Inspection date / time'),('method','Approved inspection method'),('criteria','Approved criteria / specification reference'),('measured','Actual spacing / cover / laps / dimensions'),('units','Measurement units'),('report','Inspection / material test report reference'),('laboratory','Laboratory / inspector'),('decision','Human decision: pass / fail / pending / N/A'),('authorization','Pre-pour authorization reference'),('retest','Correction / retest reference')],
}

def _test_register(sid,kind):
    columns=[{'id':key,'label':label} for key,label in REGISTER_COLUMNS[kind]]
    columns.append({'id':'na_reason','label':'N/A reason / approved inspection-plan applicability reference'})
    return {'id':sid+'_test_register','label':'Activity test-report register - repeat for each location, test and retest','type':'table','required':sid in STRUCTURAL_STAGES,'description':'For a required activity, enter actual test rows or an explicit Not applicable decision with reason and approved inspection-plan reference. Record each actual test and its approved criteria reference. Human pass/fail decisions require traceable measured results and responsible review; no numerical acceptance is prefilled. Repeat structural cycle sections for each additional floor before publishing the project template.','columns':columns}

CATALOG = (
 ('telecom_survey_default','Telecom survey - Default checklist (uploaded FDED master)','telecom','telecom_survey'),
 ('telecom_inspection_bts','Telecom inspection - Built to Suit','telecom','telecom_inspection'),
 ('telecom_inspection_colocation','Telecom inspection - Colocation and Modernization','telecom','telecom_inspection'),
 ('construction_inspection_all','Construction inspection - all stages','construction','construction_inspection'),
)

def _inspection(fid,label):
    return {'id':fid,'label':label,'type':'inspection','required':True,'description':'Verify against the approved project drawing/specification and inspection method. Record applicable reference, actual observation, date, traceable measurements with units and test report references. Record a reason when not applicable. Photos support visible condition; they do not establish concealed work, measured performance or compliance.'}

def _section(sid,title,labels,group):
    return {'id':sid,'title':title,'group':group,'fields':[_inspection(f'{sid}_{i+1:02d}',label) for i,label in enumerate(labels)]}

def _general():
    return {'id':'site_information','title':'Site and inspection information','group':'General','fields':[
        {'id':'site_id','label':'Site ID','type':'text','system':'site_id','required':True},
        {'id':'inspection_date','label':'Inspection date','type':'date','required':True},
        {'id':'inspector_name','label':'Inspector name','type':'text','required':True},
        {'id':'drawing_references','label':'Approved drawings and specification references / revisions','type':'textarea','required':True},
        {'id':'inspection_scope','label':'Inspection scope, limitations and method references','type':'textarea','required':True},
    ]}

def _rooms(rooms):
    if rooms is None:return []
    if not isinstance(rooms,list) or len(rooms)>MAX_ROOMS:raise ValueError('Provide at most 40 room instances.')
    result=[];names=set()
    for room in rooms:
        if not isinstance(room,dict) or set(room)-{'type','name','floor'}:raise ValueError('Invalid room attributes.')
        kind=room.get('type');name=room.get('name');floor=room.get('floor','')
        if kind not in ROOM_TYPES or not isinstance(name,str) or not name.strip() or len(name)>80 or not isinstance(floor,str) or len(floor)>60:raise ValueError('Provide a known room type, name and optional floor.')
        name=name.strip();floor=floor.strip();identity=(floor.casefold(),name.casefold())
        if identity in names:raise ValueError('Room names must be unique on each floor.')
        if any(ord(char)<32 for char in name+floor):raise ValueError('Room names cannot contain control characters.')
        names.add(identity);result.append({'type':kind,'name':name,'floor':floor})
    return result

def _room_labels(kind,stages):
    labels=[]
    if 'design' in stages:labels+=['Room layout, dimensions and approved drawing coordination','Room access, use and specified service provisions']
    if 'grey_structure' in stages or set(stages)&set(STRUCTURAL_STAGES):labels+=['Room walls, openings and structural interfaces','Concealed room service and embedded-item records']
    if 'mep' in stages:labels+=['Room electrical points, lighting and test references','Room ventilation, cooling and service access']
    if 'finishing' in stages:labels+=['Room floor, wall and ceiling finish condition','Room doors, glazing, joinery and hardware']
    if 'testing_handover' in stages:labels+=['Room fixtures and functional test references','Room defects, corrective action and retest record']
    wet={'bathroom','pantry','kitchen','laundry','utility'}
    if kind in wet and set(stages)&{'mep','finishing','testing_handover'}:labels+=['Wet-area waterproofing and traceable test records','Water supply, drainage connections and leak tests','Wet-area floor falls and drainage observations']
    if kind=='staircase' and set(stages)&{'grey_structure','finishing','testing_handover'}:labels+=['Stair geometry and measured drawing comparison','Stair handrails, guards, edge details and safe access']
    if kind in {'balcony','terrace'} and set(stages)&{'grey_structure','finishing','testing_handover'}:labels+=['External room waterproofing, falls and drainage','External room guards, thresholds and weathering interfaces']
    if kind in {'kitchen','pantry'} and set(stages)&{'mep','finishing','testing_handover'}:labels+=['Food preparation fixtures, extract ventilation and service isolation']
    if kind in {'plant','garage'} and set(stages)&{'design','mep','testing_handover'}:labels+=['Equipment access, ventilation and safety-system interfaces']
    if not labels:labels=['Room-specific scope and applicable stage references']
    return labels

def build_standard(key,stages=None,rooms=None):
    entry=next((item for item in CATALOG if item[0]==key),None)
    if entry is None:raise ValueError('Unknown standard checklist.')
    construction=key=='construction_inspection_all'
    if not construction and (stages not in (None,[]) or rooms not in (None,[])):raise ValueError('Room and stage selections apply only to construction.')
    selected=list(STAGES) if stages is None and construction else stages or []
    if construction and (not isinstance(selected,list) or not selected or any(not isinstance(stage,str) or stage not in STAGES for stage in selected) or len(set(selected))!=len(selected)):raise ValueError('Select valid, distinct construction stages.')
    selected=[stage for stage in STAGES if stage in selected]
    instances=_rooms(rooms) if construction else []
    if key=='telecom_survey_default':definition=deepcopy(default_definition())
    else:
        source=CONSTRUCTION if construction else BTS if key=='telecom_inspection_bts' else COLOCATION
        definition={'title':entry[1],'sections':[_general()]}
        for sid,title,labels in source:
            if construction and sid not in selected:continue
            if construction and sid=='grey_structure' and set(selected)&set(STRUCTURAL_STAGES):
                labels='Approved structural drawing and revision coordination|Structural activity sequence, hold points and interfaces|Floor and zone identification for repeated structural cycles'
            section=_section(sid,title,labels.split('|'),title)
            if construction:
                section['purpose']='Activity checks followed by repeatable, traceable inspection and test-report records.'
                section['fields'].append(_test_register(sid,'general'))
            definition['sections'].append(section)
        if construction:
            for sid,title,labels,kind in STRUCTURAL_ACTIVITIES:
                if sid not in selected:continue
                section=_section(sid,title,labels.split('|'),'Structural activities')
                section['purpose']='Identify the exact element, floor and test location; use approved criteria and record human decisions.'
                section['fields'].append(_test_register(sid,kind))
                definition['sections'].append(section)
        if construction:
            rank={stage:index for index,stage in enumerate(STAGES)}
            definition['sections'][1:]=sorted(definition['sections'][1:],key=lambda section:rank[section['id']])
        for index,room in enumerate(instances,1):
            title=room['name']+((' - '+room['floor']) if room['floor'] else '')
            section=_section(f'room_{index:02d}',title,_room_labels(room['type'],selected),'Rooms')
            section['room']=deepcopy(room)
            for field in section['fields']:
                field['room_context']=deepcopy(room)
                field['label']=title+' - '+field['label']
            definition['sections'].append(section)
        definition['technical_notice']=NOTICE
        definition['topic_sources']=deepcopy(SOURCES if construction else SOURCES[:1])
    definition['standard_catalog']={'key':key,'version':1,'industry':entry[2],'workflow_type':entry[3],'stages':selected,'rooms':deepcopy(instances)}
    return deepcopy(definition)

def catalog_entries():
    result=[]
    for key,name,industry,workflow in CATALOG:
        definition=build_standard(key)
        result.append({'key':key,'name':name,'industry':industry,'workflow_type':workflow,'sections_count':len(definition['sections']),'fields_count':sum(len(section['fields']) for section in definition['sections']),'room_types':list(ROOM_TYPES) if industry=='construction' else [],'stage_choices':[{'value':stage,'label':STAGE_LABELS.get(stage,stage.replace('_',' ').title())} for stage in STAGES] if industry=='construction' else []})
    return result
