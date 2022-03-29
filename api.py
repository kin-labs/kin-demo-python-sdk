
from pickletools import anyobject
import logging
from types import SimpleNamespace
from typing import List

from agora.utils import kin_to_quarks, quarks_to_kin
from agora.model import Invoice, LineItem, Payment, TransactionType
from agora.keys import PrivateKey, PublicKey
from agora.error import Error, TransactionErrors, InvoiceErrorReason
from agora.client import Client, Environment

from agora.webhook.events import Event
from agora.webhook.handler import WebhookHandler, AGORA_HMAC_HEADER, APP_USER_ID_HEADER, APP_USER_PASSKEY_HEADER
from agora.webhook.sign_transaction import SignTransactionRequest, SignTransactionResponse

import base58
import base64
import argparse
from dotenv import load_dotenv
import os
from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_cors import CORS, cross_origin

load_dotenv()


app = Flask(__name__)
api = Api(app)
CORS(app)


print('Kin Python SDK App')
global app_index
app_index = int(os.environ.get('APP_INDEX')) or 0
print('App Index', app_index)

global kin_client
kin_client = None

global kin_client_env
kin_client_env = Environment.TEST

global app_hot_wallet
app_hot_wallet = PrivateKey.from_string(os.environ.get('PRIVATE_KEY'))

global app_token_accounts
app_token_accounts = []

global app_user_name
app_user_name = 'App'

global app_public_key
app_public_key = app_hot_wallet.public_key.to_base58()
print('App Public Key:', app_public_key)

app_user = {
    'name': app_user_name,
    'publicKey': app_public_key,
    'privateKey': app_hot_wallet,
    'kinTokenAccounts': app_token_accounts,
}

global test_users
test_users = []
global prod_users
prod_users = []

global transactions
transactions = list([])


def save_user(name, private_key, kin_token_accounts):
    print('save_user', name, private_key, kin_token_accounts)
    new_user = {
        'name': name,
        'publicKey': private_key.public_key.to_base58(),
        'privateKey': private_key,
        'kinTokenAccounts': kin_token_accounts
    }
    print('new_user', new_user)
    if kin_client_env == Environment.TEST:
        test_users.append(new_user)

    if kin_client_env == Environment.PRODUCTION:
        prod_users.append(new_user)


def save_transaction(transaction):
    transactions.append(transaction)


def get_user_data_to_return(user):
    print('user', user)

    name = user['name']
    public_key = user['publicKey']

    return {
        'name': name,
        'publicKey': public_key
    }


def get_user(name):
    user = None
    if kin_client_env == Environment.TEST and test_users:
        user = next((x for x in test_users if x['name'] == name), None)
    if kin_client_env == Environment.PRODUCTION and prod_users:
        user = next((x for x in prod_users if x['name'] == name), None)
    if name == 'App':
        user = app_user
    return user


class Status(Resource):
    @cross_origin()
    def get(self):
        print('get /status')
        print('kin_client_env', kin_client_env)
        print('kin_client', kin_client)

        users_response = []
        env = 1
        if kin_client_env == Environment.TEST and test_users:
            users_response = list(map(get_user_data_to_return, test_users))

        if kin_client_env == Environment.PRODUCTION and prod_users:
            users_response = list(map(get_user_data_to_return, prod_users))
            env = 0

        users_response.insert(0, get_user_data_to_return(app_user))

        app_index_response = 0
        if(hasattr(kin_client, '_app_index')):
            app_index_response = kin_client._app_index

        response = {'appIndex': app_index_response,
                    'env': env,
                    'users': users_response,
                    'transactions': transactions}

        print('response', response)
        return response


api.add_resource(Status, '/status')


class Kin(Resource):
    @cross_origin()
    def post(self):
        print('post /setup', request.args)
        env_string = request.args.get('env')
        print('env_string', env_string)

        env = Environment.TEST
        if env_string == 'Prod':
            env = Environment.PRODUCTION
        print('env', env, app_index)

        new_kin_client = Client(env, app_index)
        print('new_kin_client: ', new_kin_client)

        balance = None
        try:
            # check it exists
            balance = new_kin_client.get_balance(app_hot_wallet.public_key)
        except Error as e:
            print('Error:', e)
            # if not, create it
            new_kin_client.create_account(app_hot_wallet)
            balance = new_kin_client.get_balance(app_hot_wallet.public_key)

        print('balance', balance)

        global app_token_accounts
        app_token_accounts = new_kin_client.resolve_token_accounts(
            app_hot_wallet.public_key)

        app_user['kinTokenAccounts'] = app_token_accounts
        print('app_token_accounts: ', app_token_accounts)

        global kin_client
        kin_client = new_kin_client

        global kin_client_env
        kin_client_env = env

        response = '', 201

        return response


api.add_resource(Kin, '/setup')


class Account(Resource):
    @cross_origin()
    def post(self):
        print('post /setup', request.args)
        name = request.args.get('name')
        print('name', name)

        private_key = PrivateKey.random()

        kin_client.create_account(private_key)
        kin_token_accounts = kin_client.resolve_token_accounts(
            private_key.public_key)

        save_user(name, private_key, kin_token_accounts)

        response = '', 201

        return response


api.add_resource(Account, '/account')


class Balance(Resource):
    @cross_origin()
    def get(self):
        print('post /setup', request.args)
        name = request.args.get('user')
        print('name', name)

        user = get_user(name)
        print('user', user)

        balance = kin_client.get_balance(user['privateKey'].public_key)
        print('balance', balance)

        balance_in_kin = quarks_to_kin(balance)
        print('balance_in_kin', balance_in_kin)

        response = balance_in_kin

        return response


api.add_resource(Balance, '/balance')


class Airdrop(Resource):
    @cross_origin()
    def post(self):
        print('post /setup', request.args)
        name = request.args.get('to')
        print('name', name)
        amount = request.args.get('amount')
        print('amount', amount)

        user = get_user(name)
        print('user', user)

        token_account = user['kinTokenAccounts'][0]
        print('token_account: ', token_account.to_base58())

        quarks = kin_to_quarks(amount)
        print('quarks: ', quarks)

        transaction = kin_client.request_airdrop(
            token_account, quarks)
        print('transaction', transaction)

        transaction_id = base58.b58encode(transaction)
        print('transaction_id: ', transaction_id)

        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)

        save_transaction(transaction_id_string)

        response = '', 200

        return response


api.add_resource(Airdrop, '/airdrop')


def get_transaction_type(type_string):
    if type_string == 'P2P':
        return TransactionType.P2P
    if type_string == 'Earn':
        return TransactionType.EARN
    if type_string == 'Spend':
        return TransactionType.SPEND
    return TransactionType.NONE


class MakePayment(Resource):
    @cross_origin()
    def post(self):
        print('post /send json', request.json)

        from_name = request.json.get('from')
        print('from_name', from_name)
        to_name = request.json.get('to')
        print('to_name', to_name)
        amount = request.json.get('amount')
        print('amount', amount)
        type_string = request.json.get('type')
        print('type_string', type_string)

        from_user = get_user(from_name)
        print('from_user', from_user)
        to_user = get_user(to_name)
        print('to_user', to_user)

        sender = from_user['privateKey']
        print('sender: ', sender.public_key.to_base58())

        destination = to_user['kinTokenAccounts'][0]
        print('destination: ', destination.to_base58())

        quarks = kin_to_quarks(amount)
        print('quarks: ', quarks)

        transaction_type = get_transaction_type(type_string)
        print('transaction_type: ', transaction_type)

        payment = Payment(sender, destination, transaction_type, quarks)
        print('payment: ', payment)

        transaction = kin_client.submit_payment(payment)
        print('transaction', transaction)

        transaction_id = base58.b58encode(transaction)
        print('transaction_id: ', transaction_id)

        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)

        save_transaction(transaction_id_string)

        response = '', 200

        return response


api.add_resource(MakePayment, '/send')


class GetTransaction(Resource):
    @cross_origin()
    def get(self):
        print('get /transaction', request.args)
        transaction_id = request.args.get('transaction')
        print('transaction_id: ', transaction_id)

        encoded = base58.b58encode(str.encode(transaction_id))
        # encoded = str.encode(transaction_id)
        print('encoded: ', encoded)

        transaction = kin_client.get_transaction(encoded)
        print('transaction', transaction)

        response = transaction

        return response


api.add_resource(GetTransaction, '/transaction')

webhook_secret = os.environ.get("SERVER_WEBHOOK_SECRET")
print('webhook_secret: ', webhook_secret)
webhook_handler = WebhookHandler(Environment.TEST, webhook_secret)


@app.route('/events', methods=['POST'])
def events():
    print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    print('&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&')
    status_code, request_body = webhook_handler.handle_events(
        _handle_events,
        request.headers.get(AGORA_HMAC_HEADER),
        request.data.decode('utf-8'),
    )
    print('request_body: ', request_body)
    print('status_code: ', status_code)
    return request_body, status_code


def _handle_events(received_events: List[Event]):
    print('_handle_events: ', received_events)
    for event in received_events:
        if not event.transaction_event:
            print(f'received event: {event}')
            continue

        print(
            f'transaction completed: {event.transaction_event.tx_id.hex()} {base58.b58encode(event.transaction_event.tx_id)}')
        print(base58.b58encode_(event.transaction_event.tx_id))
        print(base58.b58encode(event.transaction_event.tx_id.hex()))


@app.route('/sign_transaction', methods=["POST"])
def sign_transaction():
    print('post /sign_transaction', request)
    print('AGORA_HMAC_HEADER', request.headers.get(AGORA_HMAC_HEADER))
    print('body', request.data.decode('utf-8'))
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')

    status_code, request_body = webhook_handler.handle_sign_transaction(
        _sign_transaction,
        request.headers.get(AGORA_HMAC_HEADER),
        request.data.decode('utf-8'),
    )
    print('status_code: ', status_code)
    print('request_body: ', request_body)

    return request_body, status_code


def _sign_transaction(req: SignTransactionRequest, resp: SignTransactionResponse):
    print('_sign_transaction: ', req)
    print('raw tx_id', req.get_tx_id())
    tx_id = base58.b58encode(req.get_tx_id())
    print('tx_id: ', tx_id, tx_id.hex())

    if resp.rejected:
        print(
            f'transaction rejected: {tx_id} ({len(req.payments)} payments)')
        return

    print(
        f'transaction approved: {tx_id} ({len(req.payments)} payments)')

    # Note: This allows Agora to forward the transaction to the blockchain. However, it does not indicate that it will
    # be submitted successfully, or that the transaction will be successful. For example, the sender may have
    # insufficient funds.
    #
    # Backends may keep track of the transaction themselves using SignTransactionRequest.get_tx_hash() and rely on
    # either the Events webhook or polling to get the transaction status.
    resp.sign(app_hot_wallet)
    return


port = os.environ.get('PORT') or 3001
if __name__ == '__main__':
    app.run(debug=True, port=port)
