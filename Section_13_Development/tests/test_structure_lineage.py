"""Producer confirmation identity, causality, checkpoints and adapter consumption."""
import copy
import json
import math
import unittest
from Section_4_Features.execution.engine import Engine
from Section_4_Features.execution import checkpoint
from Section_4_Features.features import structure_events as producer
from Section_5_Market_Regime.engines import structure
from test_analytical_runner import source


def bar(i,value):return dict(symbol='BTCUSDT',interval='1m',open_time=i*60000,close_time=(i+1)*60000-1,open=value-.5,high=value+2,low=value-3,close=value,volume=100)

class StructureLineage(unittest.TestCase):
    def test_source_confirmations_preserve_origin_and_label_confirmed_prices(self):
        state=producer.new_state()
        for i,(kind,price,origin,label) in enumerate((('high',110,0,None),('low',90,1,None),('high',112,2,'HIGHER_HIGH'),('low',92,3,'HIGHER_LOW'),('high',111,4,'LOWER_HIGH'),('low',89,5,'LOWER_LOW'),('high',111,6,'EQUAL_HIGH'))):
            client=bar(i+10,100);state,events=producer.pivot(state,[],'BTCUSDT','1m',client,kind,price,origin,origin*60000)
            event=events[0];self.assertEqual(event['classification'],label);self.assertEqual(event['origin_time'],origin*60000)
            self.assertEqual(event['known_time'],client['close_time']+1);self.assertLess(event['origin_time'],event['confirmation_time'])
        state,events=producer.transition(state,[],'BTCUSDT','1m',bar(30,100),'BOS','bullishBOS',1,6)
        self.assertEqual(events[0]['pivot_id'],state['high']['id']);self.assertEqual(events[0]['origin_time'],360000)

    def test_actual_engine_events_restart_preview_and_prefix_parity(self):
        engine=Engine('BTCUSDT','1m');clients=[bar(i,100+math.sin(i/9)*14+i*.01) for i in range(350)]
        before=[engine.step(client) for client in clients[:170]]
        saved=checkpoint.dump(engine,('test',));restored=checkpoint.restore('BTCUSDT','1m',saved,('test',))
        preview=copy.deepcopy(engine);preview_packet=preview.step(clients[170],is_confirmed=False)
        self.assertEqual(preview_packet['structure_events'],'[]')
        self.assertEqual(checkpoint.dump(engine,('test',)),saved)
        after=[]
        for client in clients[170:]:
            expected=engine.step(client);self.assertEqual(expected,restored.step(client));after.append(expected)
        counts=0;ids=set()
        for client,row in zip(clients,before+after):
            for event in json.loads(row['structure_events']):
                counts+=1;self.assertNotIn(event['id'],ids);ids.add(event['id'])
                self.assertEqual(event['confirmation_time'],client['open_time']);self.assertEqual(event['known_time'],client['close_time']+1)
                if event['type'].startswith('PIVOT_'):self.assertLess(event['origin_time'],client['open_time'])
        self.assertGreater(counts,5)
        prefix=Engine('BTCUSDT','1m')
        for client,expected in zip(clients[:170],before):self.assertEqual(prefix.step(client),expected)

    def test_adapter_uses_producer_ids_deduplicates_and_rejects_future_event(self):
        p=producer.new_state();state=None
        for i,price in enumerate((110.,112.)):
            p,events=producer.pivot(p,[],'BTCUSDT','1m',bar(i+1,100),'high',price,i,i*60000)
            snap=source(i+1,structure_events=json.dumps(events));result,state=structure.evaluate(snap,previous_state=state)
            self.assertEqual(result['measurements']['new_events'][0]['id'],events[0]['id'])
        self.assertEqual(result['classification']['last_event'],'HIGHER_HIGH');self.assertEqual(result['coverage'],1)
        result,state=structure.evaluate(source(3,structure_events=json.dumps(events)),previous_state=state)
        self.assertEqual(result['measurements']['new_events'],[])
        wrong=copy.deepcopy(events);wrong[0]['id']='future';wrong[0]['known_time']=999999999
        result,_=structure.evaluate(source(4,structure_events=json.dumps(wrong)),previous_state=state)
        self.assertEqual(result['data_quality'],'INVALID');self.assertEqual(result['measurements']['new_events'],[])

    def test_candidate_fields_and_counters_cannot_manufacture_events(self):
        result,state=structure.evaluate(source(0))
        snap=source(1,bull_bos_count=10,last_structure_bos='bullishBOS');snap['features']['new_high_type']='HH'
        result,state=structure.evaluate(snap,previous_state=state)
        self.assertEqual(result['measurements']['new_events'],[])
        snap=source(2,structure_events_version=None);result,_=structure.evaluate(snap,previous_state=state)
        self.assertIn('PIVOT_EVENT_LINEAGE_UNAVAILABLE',result['quality_flags']);self.assertLess(result['coverage'],1)
