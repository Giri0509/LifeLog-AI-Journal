import unittest
from unittest.mock import patch
import test_diary_summary as summary_tests
from app.chat_history import create_conversation, list_conversations, get_messages, send_message, MessageRequest
from app.models import ChatMessage
from fastapi import HTTPException
from pydantic import ValidationError

class ChatHistoryTests(summary_tests.SummaryTests):
    def send(self, conversation_id, question='A synthetic question'):
        with patch('app.chat_history.ask_diary_chatbot', return_value={'answer':'Synthetic answer', 'sources':[{'entry_id':12, 'title':'Synthetic source', 'entry_date':'2026-10-01'}]}) as ai:
            result = send_message(conversation_id, MessageRequest(question=question), self.db, self.user)
            return result, ai.call_args

    def test_exchange_restores_from_new_session(self):
        chat = create_conversation(self.db, self.user)
        result, _ = self.send(chat['id'])
        self.assertEqual([m['role'] for m in result['messages']], ['user', 'assistant'])
        self.db.close()
        self.db = summary_tests.Session(self.engine)
        restored = get_messages(chat['id'], self.db, self.user)
        self.assertEqual(len(restored['messages']), 2)
        self.assertEqual(restored['messages'][1]['sources'][0]['entry_id'], 12)
        self.assertEqual(restored['conversation']['title'], 'A synthetic question')

    def test_conversations_are_separate(self):
        first = create_conversation(self.db, self.user)
        second = create_conversation(self.db, self.user)
        self.send(first['id'], 'First chat question')
        result, call = self.send(second['id'], 'Second chat question')
        self.assertEqual(call.kwargs['history'], [])
        self.assertEqual(get_messages(first['id'], self.db, self.user)['messages'][0]['content'], 'First chat question')
        self.assertEqual(list_conversations(self.db, self.user)['conversations'][0]['id'], second['id'])

    def test_followups_receive_ordered_bounded_history(self):
        chat = create_conversation(self.db, self.user)
        for index in range(7):
            self.send(chat['id'], f'Question {index}')
        _, call = self.send(chat['id'], 'Followup')
        history = call.kwargs['history']
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]['content'], 'Question 2')
        self.assertEqual(history[-1]['role'], 'assistant')
        self.assertEqual(len(get_messages(chat['id'], self.db, self.user)['messages']), 16)

    def test_ai_failure_saves_no_partial_exchange(self):
        chat = create_conversation(self.db, self.user)
        with patch('app.chat_history.ask_diary_chatbot', side_effect=RuntimeError('sensitive detail')):
            with self.assertRaises(HTTPException) as caught:
                send_message(chat['id'], MessageRequest(question='Question'), self.db, self.user)
        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn('sensitive', caught.exception.detail)
        self.assertEqual(get_messages(chat['id'], self.db, self.user)['messages'], [])
        self.send(chat['id'])
        self.assertEqual(len(get_messages(chat['id'], self.db, self.user)['messages']), 2)

    def test_commit_failure_rolls_back_both_messages(self):
        chat = create_conversation(self.db, self.user)
        with patch('app.chat_history.ask_diary_chatbot', return_value={'answer':'Test answer', 'sources':[]}), patch.object(self.db, 'commit', side_effect=RuntimeError('failure')):
            with self.assertRaises(HTTPException):
                send_message(chat['id'], MessageRequest(question='Question'), self.db, self.user)
        self.assertEqual(self.db.query(ChatMessage).count(), 0)
        self.assertEqual(get_messages(chat['id'], self.db, self.user)['conversation']['title'], 'New chat')

    def test_missing_conversation_and_invalid_question(self):
        with self.assertRaises(HTTPException) as caught:
            get_messages(99999, self.db, self.user)
        self.assertEqual(caught.exception.status_code, 404)
        with self.assertRaises(HTTPException) as caught:
            send_message(99999, MessageRequest(question='Question'), self.db, self.user)
        self.assertEqual(caught.exception.status_code, 404)
        chat = create_conversation(self.db, self.user)
        with self.assertRaises(HTTPException):
            send_message(chat['id'], MessageRequest(question='   '), self.db, self.user)
        with self.assertRaises(ValidationError):
            MessageRequest(question='x' * 4001)

if __name__ == '__main__':
    unittest.main()
