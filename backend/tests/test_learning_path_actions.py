import unittest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.api.concepts import get_learning_path
from app.models.concept import Concept
from app.models.concept_relation import ConceptRelation
from app.models.problem import Problem
from app.models.problem_concept import ProblemConcept
from app.models.problem_attempt import ProblemAttempt

class LearningPathActionTests(unittest.TestCase):
    def test_prerequisite_reason_exercise_and_latest_error_drive_recommendation(self):
        engine=create_engine('sqlite:///:memory:');Base.metadata.create_all(engine);db=sessionmaker(bind=engine)()
        base=Concept(name='逻辑',type='concept');target=Concept(name='逆反命题',type='theorem');problem=Problem(title='逻辑练习',content='解释逻辑等价',solution='等价');db.add_all([base,target,problem]);db.commit()
        edge=ConceptRelation(source_concept_id=base.id,target_concept_id=target.id,relation='prerequisite');db.add(edge);db.add(ProblemConcept(problem_id=problem.id,concept_id=base.id));db.add(ProblemAttempt(problem_id=problem.id,answer='错误',correctness='incorrect',status='reviewed',created_at=datetime.utcnow()));db.commit()
        data=get_learning_path(target.id,db=db)
        self.assertEqual([x['id'] for x in data['steps']],[base.id,target.id])
        step=data['steps'][0];self.assertEqual(step['problems'][0]['id'],problem.id)
        self.assertEqual(step['relation_ids'],[edge.id]);self.assertIn('逆反命题',step['reason'])
        self.assertEqual(step['current_state'],'needs_review');self.assertEqual(data['recommended_concept_id'],base.id)
        self.assertIn('没有关联练习',data['steps'][1]['reason'])
        db.add(ConceptRelation(source_concept_id=target.id,target_concept_id=base.id,relation='prerequisite'));db.commit()
        self.assertTrue(get_learning_path(target.id,db=db)['cycle_detected'])
        db.close()
