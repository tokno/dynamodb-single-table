import sys
from dynamodb_single_table import *


TableHolder = create_table_holder(sys.argv[1])

class BaseEntity(TableHolder, Entity):
    ...


class User(BaseEntity):
    pk = PK('USER#{user_id}')
    sk = SK('USER#{user_id}')
    gsi1_pk = PK('USER')
    gsi1_sk = SK('USER#{user_id}')

    attributes = {
        'username': {
            'type': 'string',
        },
        'email_address': {
            'type': 'string',
        },
    }


class Quiz(BaseEntity):
    pk = PK('USER#{user_id}')
    sk = SK('QUIZ#{quiz_id}')
    gsi1_pk = PK('DATE#{date}')
    gsi1_sk = SK('QUIZ#{quiz_id}')

    attributes = {
        'list_id': {
            'type': 'integer',
        },
        'date': {
            'type': 'string',
        },
        'details': {
            'type': 'dict',
        },
    }


class Sentence(BaseEntity):
    pk = PK('USER#{user_id}')
    sk = SK('SENTENCE#{sentence_id}')
    gsi1_pk = PK('DATE#{date}')
    gsi1_sk = SK('SENTENCE#{sentence_id}')

    attributes = {
        'list_id': {
            'type': 'integer',
        },
        'date': {
            'type': 'string',
        },
        'word_id': {
            'type': 'integer',
        },
        'sentence': {
            'type': 'string',
        },
    }


class ListSubscription(BaseEntity):
    pk = PK('USER#{user_id}')
    sk = SK('LIST#{list_id}')
    gsi1_pk = PK('USER')
    gsi1_sk = SK('USER#{user_id}#LIST#{list_id}#{character_set_preference}')

    attributes = {
        'character_set_preference': {
            'type': 'string',
        },
        'list_name': {
            'type': 'string',
        },
        'subecribed_status': {
            'type': 'string',
        },
    }


class List(BaseEntity):
    pk = PK('LIST#{list_id}')
    sk = SK('LIST#{list_id}')
    gsi1_pk = PK('CREATED_BY#{user_id}')
    gsi1_sk = SK('LIST#{list_id}')

    attributes = {
        'list_name': {
            'type': 'string',
        },
        'difficulty_level': {
            'type': 'string',
        },
    }


class WordInList(BaseEntity):
    pk = PK('LIST#{list_id}')
    sk = SK('WORD#{word_id}')

    attributes = {
        'word': {
            'type': 'dict',
        },
    }


class Word(BaseEntity):
    pk = PK('WORD#{word_id}')
    sk = SK('WORD#{word_id}')

    attributes = {
        'simplified': {
            'type': 'string',
        },
        'traditional': {
            'type': 'string',
        },
        'pinyin': {
            'type': 'string',
        },
        'definition': {
            'type': 'string',
        },
    }


class SentWord(BaseEntity):
    pk = PK('LIST#{list_id}')
    sk = SK('DATESENT#{date}')

    attributes = {
        'word': {
            'type': 'dict',
        },
        'word_id': {
            'type': 'string',
        },
    }


class AccessPattern(TableHolder):
    # User profiles - Retrieve individual user details including subscriptions, quiz results, practice sentences, etc.
    @classmethod
    def get_user_profiles(cls, user_id):
        ...

    # Send daily emails - Retrieve all users and their subscriptions.
    @classmethod
    def get_all_users_and_their_subscriptions(cls):
        ...

    # Leaderboards - Retrieve all users' quiz results and practice sentences for a given day.
    @classmethod
    def get_all_users_quiz_results_and_practice_sentences(cls, date):
        ...

    # Select daily word - Retrieve all words for a given list.
    @classmethod
    def get_all_words_for_list(cls, list_id):
        ...

    # Review words - Retrieve past words sent chronologically and grouped by list.
    @classmethod
    def get_words_chronologically_and_group_by_list(cls):
        ...

    # List creation - Retrieve all words (to create a new list).
    @classmethod
    def get_all_words(cls):
        ...


if __name__ == '__main__':
    # create user
    User.create(
        user_id='12345',
        username='小沈',
        email_address='user12345@example.com'
    )

    # create quiz
    Quiz.create(
        user_id=12345,
        quiz_id=123,
        list_id=1,
        date='2021-06-08',
        details={
            'Question count': 10,
            'Quiz percentage': '50%'
        }
    )

    # create sentence
    Sentence.create(
        user_id=12345,
        sentence_id=123,
        list_id=1,
        date='2021-06-08',
        word_id=123,
        sentence='今天天气真好'
    )

    # create sentence
    Sentence.create(
        user_id=12345,
        sentence_id=321,
        list_id=1,
        date='2021-06-08',
        word_id=321,
        sentence='今天天气真好'
    )

    # create list subscription
    ListSubscription.create(
        user_id=12345,
        list_id=1,
        character_set_preference='simplified',
        list_name='HSK Level 1',
        subecribed_status='subscribed'
    )

    # create list
    List.create(
        list_id=123,
        list_name='HSK Level 1',
        user_id='ADMIN',
        difficulty_level='beginner'
    )

    # create word in list
    WordInList.create(
        list_id=1,
        word_id=123,
        word={}
    )

    # create word
    Word.create(
        word_id=123,
        simplified='今天',
        traditional='今天',
        pinyin='jin tian',
        definition='today; at the present; now'
    )

    # create sent word
    SentWord.create(
        list_id='1',
        date='2021-06-08',
        word={},
        word_id='123'
    )

    result = TableHolder.multiple_entity_query(
        pk='USER#12345',
    )

    result = Sentence.find_by_key_prefix(user_id='12345')

    print(result)
