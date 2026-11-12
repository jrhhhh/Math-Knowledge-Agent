import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from fastapi import HTTPException
from app.api.graph_navigation import validate_groups,suggest,SuggestInput

class NavigationTests(unittest.TestCase):
    def test_partition_and_missing_nodes(self):
        groups=validate_groups(json.dumps({'groups':[{'name':'极限','concept_ids':[1,2]},{'name':'积分','concept_ids':[3]}]}),[1,2,3,4])
        self.assertEqual(groups[-1],{'name':'尚未归类','concept_ids':[4]})
        self.assertEqual({i for g in groups for i in g['concept_ids']},{1,2,3,4})
    def test_duplicate_unknown_or_bad_groups_rejected(self):
        for groups in [[{'name':'A','concept_ids':[1]},{'name':'B','concept_ids':[1,2]}],[{'name':'A','concept_ids':[1]},{'name':'B','concept_ids':[99]}],[{'name':'A','concept_ids':[1]},{'name':'A','concept_ids':[2]}]]:
            with self.assertRaises(ValueError):validate_groups(json.dumps({'groups':groups}),[1,2,3,4])
    def test_read_only_response_and_provider_failure(self):
        db=MagicMock();db.query.return_value.filter.return_value.all.return_value=[SimpleNamespace(id=i,name='概念'+str(i),field='分析',description='说明') for i in [1,2,3,4]]
        reply=json.dumps({'groups':[{'name':'主题一','concept_ids':[1,2]},{'name':'主题二','concept_ids':[3,4]}]})
        with patch('app.api.graph_navigation.call_deepseek',return_value=reply):
            result=suggest(SuggestInput(concept_ids=[1,2,3,4]),db);self.assertFalse(result['saved'])
        db.add.assert_not_called();db.commit.assert_not_called()
        with patch('app.api.graph_navigation.call_deepseek',side_effect=RuntimeError('provider')):
            with self.assertRaises(HTTPException) as error:suggest(SuggestInput(concept_ids=[1,2,3,4]),db)
            self.assertEqual(error.exception.status_code,503)
    def test_unknown_ids_and_duplicates(self):
        db=MagicMock();db.query.return_value.filter.return_value.all.return_value=[]
        with self.assertRaises(HTTPException):suggest(SuggestInput(concept_ids=[1,1,2,3]),db)
        with self.assertRaises(HTTPException):suggest(SuggestInput(concept_ids=[1,2,3,4]),db)
