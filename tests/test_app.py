from datetime import date, timedelta
from pathlib import Path
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)


def financial():
    return {'balance':850,'paycheck':500,'payday':(date.today()+timedelta(days=10)).isoformat(),
            'cadence':14,'rent':600,'rent_date':(date.today()+timedelta(days=7)).isoformat(),
            'groceries':50,'subscriptions':55}


def test_static_html_and_files():
    for path in ['/', '/static/style.css', '/static/app.js', '/api/demo-csv','/api/status']:
        assert client.get(path).status_code == 200


def test_security_and_finance():
    r = client.post('/api/payment',json={'financial':financial(), 'message':'URGENT! Pay immediately', 'payment':450,'days':30})
    assert r.status_code==200, r.text
    data=r.json()
    assert data['security']['alerts']
    assert len(data['pay_now']['points']) == 30
    assert data['pay_now']['lowest'] < 0


def test_subscription_savings_visible():
    payload={'financial':financial(), 'price':500,'cheaper':250,'days':60,
             'selected_savings':52.99, 'include_savings':True}
    r = client.post('/api/purchase',json=payload)
    assert r.status_code == 200, r.text
    data=r.json()
    assert data['ending_improvement']==52.99
    assert data['scenarios']['Buy now']['lowest']==data['baseline_buy_now']['lowest']
    payload['days']=30
    assert client.post('/api/purchase',json=payload).json()['ending_improvement']==0


def test_transaction_analysis():
    demo=client.get('/api/demo-csv').text
    result=client.post('/api/transactions',json={'csv_text':demo})
    assert result.status_code==200, result.text
    r=result.json()
    assert r['transactions']==15
    assert r['monthly_estimate']==62.98
    assert any(item['Change']==3.00 for item in r['recurring'])


def test_goal_coach_offline():
    data={'financial':financial(),'goal':1200,'saved':200,'months':4,'selected_savings':52.99}
    goal=client.post('/api/goal',json=data)
    assert goal.status_code==200
    assert goal.json()['plan']['monthly_target']==250
    assert abs(goal.json()['adjusted_plan']['monthly_headroom'] - goal.json()['plan']['monthly_headroom'] - 52.99) < 0.001
    chat=client.post('/api/coach',json={**data,'question':'How do I reach my goal?','message':'urgent'})
    assert chat.status_code==200
    assert chat.json()['mode']=='offline_rules'


def test_bad_csv_and_incorrect_dates():
    assert client.post('/api/transactions',json={'csv_text':'abc,def\n1,2'}).status_code==422
    f=financial();f['payday']='2020-01-01'
    assert client.post('/api/payment',json={'financial':f}).status_code==422
