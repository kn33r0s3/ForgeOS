"""Authoritative SANDBOX/TEST source-to-cash-to-learning HTTP proof.
All people/amounts are synthetic operator inputs; ZERO real customer claims.
"""
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app import models
from app.database import Base, get_db
from app.main import app
from app.services import source_manager, lessons_engine

@pytest.fixture
def httpdb(monkeypatch):
    from app import security
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "")
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    source_manager.seed_default_sources(db)
    def dependency():
        try:
            yield db
        except Exception:
            db.rollback()
            raise
    app.dependency_overrides[get_db] = dependency
    # No app lifespan: schema is explicitly initialized on this isolated DB.
    client = TestClient(app, raise_server_exceptions=False)
    yield client, db, engine
    client.close(); app.dependency_overrides.clear(); db.close(); engine.dispose()

TEXTS = [
    'Independent repair shops lose hours every week manually explaining appointment status; no-shows cost about $500 a month per shop. Owners currently use paper and would pay for a way to cut no-shows. A $99/month reminder service is a hypothesis to test.',
    'Repair shops report appointment no-shows every week. Staff manually call customers using a spreadsheet; missed appointments cost $600 monthly. They need an automated reminder service and would pay if it reduced missed bookings.',
    'Five independent repair shops struggle with missed appointments every day. Manual reminder calls take 6 hours a week, costing $400 per month. Shop owners need an easier appointment reminder tool.',
]

def source_to_experiment(client, db):
    for text in TEXTS:
        res = client.post('/observer/observe', json={'content': 'SANDBOX/TEST source input: '+text, 'source': 'manual'})
        assert res.status_code == 200, res.text
    res = client.post('/forge/cycle?data_scope=SANDBOX')
    assert res.status_code == 200, res.text
    cycle = res.json()
    assert cycle['opportunities_discovered'] >= 1
    assert db.query(models.Signal).count() == 3
    assert db.query(models.Evidence).count() >= 3
    assert db.query(models.Pattern).count() >= 1
    opp = db.query(models.Opportunity).filter(models.Opportunity.problem.contains('repair')).first()
    assert opp and opp.score > 0
    res = client.post(f'/orchestrate/{opp.id}/advance?data_scope=SANDBOX&price_assumption=99')
    assert res.status_code == 200, res.text
    state = res.json()
    assert 'repair' in state['opportunity']['target_customer'].lower()
    assert state['experiment']['stage'] == 'APPROVAL_REQUIRED'
    return opp.id, state


def response_payload():
    return {'data_scope':'SANDBOX','actual':'SANDBOX/TEST: five hypothetical owners reject $99/month but three indicate $40/month. All five confirm no-show pain. This is not a real interview.',
            'actual_value':40, 'unit':'USD', 'success':False, 'conversions':3,
            'source':'SANDBOX synthetic operator fixture',
            'contacts':[{'name':f'SANDBOX Shop {i}','stage':'interested' if i < 3 else 'lead',
                         'notes':'confirmed no-show pain; willing $40' if i < 3 else 'confirmed no-show pain; price unsure'} for i in range(5)]}


def ready(client, oid):
    assert client.post(f'/orchestrate/{oid}/approve?data_scope=SANDBOX').status_code == 200
    res=client.post(f'/orchestrate/{oid}/execute?data_scope=SANDBOX')
    assert res.status_code == 200, res.text
    assert res.json()['experiment']['stage'] == 'OUTCOME_PENDING'


def test_source_to_cash_to_learning_again_http_SANDBOX(httpdb):
    c, db, engine = httpdb
    oid, state = source_to_experiment(c, db)
    assert '$99' in '\n'.join(state['experiment']['required_inputs'])
    assert c.post(f'/orchestrate/{oid}/execute?data_scope=SANDBOX').status_code == 409
    assert c.post(f'/orchestrate/{oid}/outcome',json=response_payload()).status_code == 422
    ready(c,oid)
    assert db.query(models.Outcome).count() == 0  # executing task is not customer evidence
    res=c.post(f'/orchestrate/{oid}/outcome',json=response_payload())
    assert res.status_code == 200, res.text
    assert res.json()['experiment']['stage'] == 'LEARNED'
    assert db.query(models.Outcome).count() == 1
    assert db.query(models.LearningEvent).count() == 1
    lesson=db.query(models.Lesson).one()
    assert lesson.data_scope == 'SANDBOX' and '40' in lesson.summary and '99' in lesson.summary
    assert lesson.source_learning_event_ids
    lessons_engine.consolidate_learning_event(db,db.query(models.LearningEvent).one())
    assert lesson.hit_count == 1
    assert c.post(f'/orchestrate/{oid}/outcome',json=response_payload()).status_code == 200
    assert db.query(models.Outcome).count() == 1
    changed=c.post(f'/orchestrate/{oid}/next-decision?data_scope=SANDBOX')
    assert changed.status_code==200, changed.text
    assert 'Modify pricing' in changed.json()['title']
    assert '40' in changed.json()['rationale'] and 'Recalled lesson' in changed.json()['rationale']
    real=c.post(f'/orchestrate/{oid}/next-decision?data_scope=REAL').json()
    assert 'Price sensitivity' not in real['rationale']
    gate=c.post(f'/orchestrate/{oid}/product',json={'data_scope':'SANDBOX'})
    assert gate.status_code == 200 and gate.json()['status']=='created',gate.text
    pid=gate.json()['product_id']
    product=c.get(f'/products/{pid}').json()
    assert product['actual_revenue']==0 and product['launch_state']=='not_launched'
    assert 'repair' in product['target_customer'].lower()
    channel=c.post(f'/products/{pid}/channels',json={'channel_type':'direct_sales','name':'SANDBOX manual pilot','data_scope':'SANDBOX'})
    assert channel.status_code==200,channel.text
    cid=channel.json()['id']
    contact=c.post(f'/products/channels/{cid}/customers',json={'stage':'paid_customer','contact_name':'SANDBOX payer','data_scope':'SANDBOX'})
    assert contact.status_code==422,contact.text
    assert c.get(f'/products/{pid}').json()['actual_revenue']==0 # event alone is not cash
    params={'outcome_type':'ACTUAL_REVENUE','product_id':pid,'actual_value':99,'unit':'USD','data_scope':'SANDBOX','source':'SANDBOX TEST payment fixture','idempotency_key':'sandbox-payment-1'}
    for _ in range(2):
        cash=c.post('/forge/outcomes',params=params)
        assert cash.status_code==200,cash.text
    assert cash.json()['label']=='SANDBOX/TEST ACTUAL'
    assert c.get(f'/products/{pid}').json()['actual_revenue']==99
    assert db.query(models.LearningEvent).filter_by(product_id=pid,data_scope='SANDBOX').count()==1
    assert db.query(models.Outcome).filter_by(data_scope='REAL',outcome_type='ACTUAL_REVENUE').count()==0
    pipeline=c.get('/orchestrate/flow?data_scope=REAL').json()['pipeline']
    assert pipeline['actual_revenue']==0, pipeline
    # Every GET must be free of flushes, updates and commits.
    statements=[]
    def capture(conn, cursor, statement, *args):
        if statement.split()[0].upper() in {'INSERT','UPDATE','DELETE'}: statements.append(statement)
    event.listen(engine,'before_cursor_execute',capture)
    for url in ['/orchestrate/flow?data_scope=SANDBOX',f'/products/{pid}','/products/pipeline']:
        assert c.get(url).status_code==200
    event.remove(engine,'before_cursor_execute',capture)
    assert not statements


def test_transaction_failure_rolls_back_every_stage_and_retry(httpdb, monkeypatch):
    c,db,_=httpdb
    oid,_=source_to_experiment(c,db);ready(c,oid)
    actual_commit=db.commit
    def fail(): raise RuntimeError('SANDBOX injected commit failure')
    monkeypatch.setattr(db,'commit',fail)
    assert c.post(f'/orchestrate/{oid}/outcome',json=response_payload()).status_code==500
    assert db.query(models.Outcome).count()==0
    assert db.query(models.LearningEvent).count()==0
    assert db.query(models.Lesson).count()==0
    assert db.query(models.CustomerEvent).count()==0
    exp=db.query(models.Experiment).filter_by(opportunity_id=oid,data_scope='SANDBOX').first()
    assert exp.status=='in_progress' and exp.conversions is None
    monkeypatch.setattr(db,'commit',actual_commit)
    assert c.post(f'/orchestrate/{oid}/outcome',json=response_payload()).status_code==200


def test_rejection_no_outcome_and_scope_mismatch(httpdb):
    c,db,_=httpdb
    oid,_=source_to_experiment(c,db)
    assert c.post(f'/orchestrate/{oid}/product',json={'data_scope':'SANDBOX'}).json()['status']=='not_validated'
    assert c.post(f'/orchestrate/{oid}/reject?data_scope=SANDBOX').status_code==200
    assert c.post(f'/orchestrate/{oid}/execute?data_scope=SANDBOX').status_code==409
    assert c.post(f'/orchestrate/{oid}/outcome',json=response_payload()).status_code==422
    assert c.post(f'/orchestrate/{oid}/approve?data_scope=SANDBOX').status_code==409
    assert db.query(models.Outcome).count()==0
    product=c.post('/products',json={'name':'SANDBOX','offer':'hypothesis','data_scope':'SANDBOX'}).json()
    assert c.post(f"/products/{product['id']}/channels",json={'name':'bad','channel_type':'direct_sales','data_scope':'REAL'}).status_code==422
    for unit,scope in [('USD','REAL'),('NPR','SANDBOX')]:
        assert c.post('/forge/outcomes',params={'outcome_type':'ACTUAL_REVENUE','product_id':product['id'],'actual_value':99,'unit':unit,'data_scope':scope}).status_code==422


def test_ingestion_failure_and_retry(httpdb,monkeypatch):
    from app.services import signal_processor
    c,db,_=httpdb
    original=signal_processor.process_signal
    monkeypatch.setattr(signal_processor,'process_signal',lambda *a: (_ for _ in ()).throw(RuntimeError('ingestion failed')))
    assert c.post('/observer/observe',json={'content':TEXTS[0],'source':'manual'}).status_code==500
    assert db.query(models.Signal).count()==0
    monkeypatch.setattr(signal_processor,'process_signal',original)
    assert c.post('/observer/observe',json={'content':TEXTS[0],'source':'manual'}).status_code==200


def test_scoring_failure_is_honest_and_next_cycle_recovers(httpdb,monkeypatch):
    from app.services import opportunity_engine
    c,db,_=httpdb
    for t in TEXTS:
        assert c.post('/observer/observe',json={'content':t,'source':'manual'}).status_code==200
    original=opportunity_engine.run_autonomous_opportunity_discovery
    monkeypatch.setattr(opportunity_engine,'run_autonomous_opportunity_discovery',lambda *a: (_ for _ in ()).throw(RuntimeError('TEST scoring failed')))
    assert c.post('/forge/cycle?data_scope=SANDBOX').status_code==500
    assert db.query(models.Outcome).count()==0
    monkeypatch.setattr(opportunity_engine,'run_autonomous_opportunity_discovery',original)
    assert c.post('/forge/cycle?data_scope=SANDBOX').status_code==200


def test_product_cash_commit_failure_has_no_orphan_learning(httpdb,monkeypatch):
    c,db,_=httpdb
    p=c.post('/products',json={'name':'TEST','offer':'TEST','data_scope':'SANDBOX'}).json()
    actual_commit=db.commit
    monkeypatch.setattr(db,'commit',lambda: (_ for _ in ()).throw(RuntimeError('TEST failed commit')))
    params={'product_id':p['id'],'outcome_type':'ACTUAL_REVENUE','actual_value':99,'data_scope':'SANDBOX','idempotency_key':'test-retry'}
    assert c.post('/forge/outcomes',params=params).status_code==500
    assert db.query(models.Outcome).count()==db.query(models.LearningEvent).count()==db.query(models.Lesson).count()==0
    monkeypatch.setattr(db,'commit',actual_commit)
    assert c.post('/forge/outcomes',params=params).status_code==200
    assert c.post('/forge/outcomes',params=params).status_code==200
    assert db.query(models.Outcome).count()==1


def test_duplicate_contacts_and_customer_rejection_do_not_validate(httpdb):
    c,db,_=httpdb
    oid,_=source_to_experiment(c,db);ready(c,oid)
    payload=response_payload()
    payload['contacts']=[{'name':'Same TEST shop','stage':'interested','notes':'confirmed pain'}]*5
    assert c.post(f'/orchestrate/{oid}/outcome',json=payload).status_code==200
    gate=c.post(f'/orchestrate/{oid}/product',json={'data_scope':'SANDBOX'}).json()
    assert gate['status']=='not_validated' and gate['confirm_problem']==1
    payload['success']=True
    assert c.post(f'/orchestrate/{oid}/outcome',json=payload).status_code==422
    assert c.get('/orchestrate/flow').json()['pipeline']['actual_revenue']==0


def test_sandbox_direct_money_does_not_train_real_confidence(httpdb):
    from app.services import money_engine
    c,db,_=httpdb
    oid,_=source_to_experiment(c,db);ready(c,oid)
    o=db.get(models.Opportunity,oid)
    before=(o.market_confidence,o.revenue_confidence,o.estimated_revenue)
    e=db.query(models.Experiment).filter_by(opportunity_id=oid,data_scope='SANDBOX').first()
    money_engine.record_revenue_result(db,e.id,'SANDBOX payment test',revenue=99,data_scope='SANDBOX')
    assert (o.market_confidence,o.revenue_confidence,o.estimated_revenue)==before
    assert db.query(models.Outcome).filter_by(data_scope='REAL').count()==0
    assert db.query(models.LearningEvent).filter_by(data_scope='SANDBOX').count()==1
