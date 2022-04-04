import os
import string
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, Response, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

import base58

from agora.utils import kin_to_quarks, quarks_to_kin
from agora.model import Payment, TransactionType
from agora.keys import PrivateKey, PublicKey
from agora.client import Client, Environment

from agora.webhook.events import Event
from agora.webhook.handler import WebhookHandler, AGORA_HMAC_HEADER
from agora.webhook.sign_transaction import SignTransactionRequest, SignTransactionResponse

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=["*"],
    allow_headers=["*"],
)


print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print(' - Kin Python SDK App')

app_index = int(os.environ.get('APP_INDEX')) or 0
print(' - App Index', app_index)

kin_client = None

kin_client_env = Environment.TEST

app_hot_wallet = PrivateKey.from_string(os.environ.get('PRIVATE_KEY'))

app_token_accounts = []

app_user_name = 'App'

app_public_key = app_hot_wallet.public_key.to_base58()
print(' - App Public Key:', app_public_key)

app_user = {
    'name': app_user_name,
    'publicKey': app_public_key,
    'privateKey': app_hot_wallet,
    'kinTokenAccounts': app_token_accounts,
}

test_users = []
prod_users = []

transactions = list([])


def save_user(name: string, private_key: PrivateKey, kin_token_accounts: List[PublicKey]):
    print('save_user: ', name, private_key, kin_token_accounts)
    # %%%%%%%%%%%% IMPORTANT %%%%%%%%%%%%
    # TODO - Save your account data securely
    new_user = {
        'name': name,
        'publicKey': private_key.public_key.to_base58(),
        'privateKey': private_key,
        'kinTokenAccounts': kin_token_accounts
    }

    print('kin_client_env: ', kin_client_env)
    if kin_client_env == Environment.TEST:
        global test_users
        test_users.append(new_user)
        print('save_user test_users: ', test_users)

    if kin_client_env == Environment.PRODUCTION:
        global prod_users
        prod_users.append(new_user)


def save_transaction(transaction: string):
    # TODO save your transaction data if required
    transactions.append(transaction)


Sanitised_User_Data = {

}


def get_sanitised_user_data(user: string):
    name = user['name']
    public_key = user['publicKey']

    return {
        'name': name,
        'publicKey': public_key
    }


def get_user(name: string):
    user = None
    if kin_client_env == Environment.TEST and test_users:
        user = next((x for x in test_users if x['name'] == name), None)
    if kin_client_env == Environment.PRODUCTION and prod_users:
        user = next((x for x in prod_users if x['name'] == name), None)
    if name == 'App':
        user = app_user
    print('user: ', user)
    return user


@app.get("/status")
async def return_server_status():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /status')
    print('kin_client_env', kin_client_env)
    print('kin_client', kin_client)

    users_response = []
    env = 1
    print('test_users: ', test_users)
    if kin_client_env == Environment.TEST and test_users:
        users_response = list(map(get_sanitised_user_data, test_users))

    if kin_client_env == Environment.PRODUCTION and prod_users:
        users_response = list(map(get_sanitised_user_data, prod_users))
        env = 0

    print('users_response: ', users_response)
    users_response.insert(0, get_sanitised_user_data(app_user))
    print('users_response: ', users_response)

    app_index_response = 0
    if(hasattr(kin_client, '_app_index')):
        app_index_response = kin_client._app_index

    data = {'appIndex': app_index_response,
            'env': env,
            'users': users_response,
            'transactions': transactions}

    return JSONResponse(status_code=200, content=jsonable_encoder(data), media_type='application/json')


def reset_on_setup_error():
    global app_token_accounts
    app_token_accounts = []
    app_user['kinTokenAccounts'] = app_token_accounts

    global kin_client
    kin_client = None

    global kin_client_env
    kin_client_env = Environment.TEST


@app.post('/setup')
async def setup_client(env: str):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /setup')

    try:
        environment = Environment.TEST
        if env == 'Prod':
            environment = Environment.PRODUCTION
        print('environment', environment, app_index)

        new_kin_client = Client(environment, app_index)
        print('new_kin_client: ', new_kin_client)

        balance = None
        try:
            # check it exists
            balance = new_kin_client.get_balance(app_hot_wallet.public_key)
        except Exception as e:
            print('Error:', e)
            # if not, create it
            new_kin_client.create_account(app_hot_wallet)
            balance = new_kin_client.get_balance(app_hot_wallet.public_key)
        print('balance', balance)

        global app_token_accounts
        app_token_accounts = new_kin_client.resolve_token_accounts(
            app_hot_wallet.public_key)
        app_user['kinTokenAccounts'] = app_token_accounts

        global kin_client
        kin_client = new_kin_client

        global kin_client_env
        if env == 'Test':
            kin_client_env = Environment.TEST
        if env == 'Prod':
            kin_client_env = Environment.PRODUCTION

        print('Setup successful')
        return Response(status_code=201)

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        reset_on_setup_error()

        return Response(status_code=status.HTTP_418_IM_A_TEAPOT)


@app.post('/account')
async def account(name: str):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /account')

    try:
        print('name', name)

        private_key = PrivateKey.random()

        kin_client.create_account(private_key)
        kin_token_accounts = kin_client.resolve_token_accounts(
            private_key.public_key)

        print('save_user: ', save_user)
        save_user(name, private_key, kin_token_accounts)
        print('Account created', private_key.public_key.to_base58())

        return Response(status_code=201)

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        return Response(status_code=status.HTTP_418_IM_A_TEAPOT)


@app.get('/balance')
async def balance(user: str):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /balance')

    try:
        print('user', user)
        user_private_key = get_user(user)['privateKey']
        print('user_private_key: ', user_private_key)
        balance = kin_client.get_balance(user_private_key.public_key)
        print('balance', balance)

        balance_in_kin = quarks_to_kin(balance)
        print('balance_in_kin', balance_in_kin)

        return Response(status_code=200, content=balance_in_kin)

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        return Response(status_code=status.HTTP_418_IM_A_TEAPOT)


@app.post('/airdrop')
async def airdrop(to: str, amount: str):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /airdrop')

    try:
        token_account = get_user(to)['kinTokenAccounts'][0]
        print('token_account: ', token_account.to_base58())

        quarks = kin_to_quarks(amount)
        print('quarks: ', quarks)

        transaction = kin_client.request_airdrop(
            token_account, quarks)

        transaction_id = base58.b58encode(transaction)
        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)

        return Response(status_code=201)

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        return Response(status_code=status.HTTP_418_IM_A_TEAPOT)


def get_transaction_type(type_string):
    if type_string == 'P2P':
        return TransactionType.P2P
    if type_string == 'Earn':
        return TransactionType.EARN
    if type_string == 'Spend':
        return TransactionType.SPEND
    return TransactionType.NONE


@app.post('/send')
async def send(request: Request):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /send')

    try:
        body = await request.json()
        from_name = body['from']
        print('from_name', from_name)
        to_name = body['to']
        print('to_name', to_name)
        amount = body['amount']
        print('amount', amount)
        type_string = body['type']
        print('type_string', type_string)

        from_user = get_user(from_name)
        to_user = get_user(to_name)

        sender = from_user['privateKey']
        print('sender: ', sender.public_key.to_base58())

        destination = to_user['kinTokenAccounts'][0]
        print('destination: ', destination.to_base58())

        quarks = kin_to_quarks(amount)
        print('quarks: ', quarks)

        transaction_type = get_transaction_type(type_string)
        print('transaction_type: ', transaction_type)

        payment = Payment(sender, destination, transaction_type, quarks)
        transaction = kin_client.submit_payment(payment)
        transaction_id = base58.b58encode(transaction)
        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)

        save_transaction(transaction_id_string)

        return Response(status_code=201)

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        return Response(status_code=status.HTTP_418_IM_A_TEAPOT)


def get_sanitised_payment(payment):
    print('payment: ', payment)
    return {
        'type': payment.tx_type,
        'quarks': payment.quarks,
        'sender': payment.sender.to_base58(),
        'destination': payment.destination.to_base58()
    }


@app.get('/transaction')
async def transaction(transaction: str):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /transaction')

    try:
        print('transaction: ', transaction)

        decoded = base58.b58decode(transaction)
        transaction_data = kin_client.get_transaction(decoded)

        payments = list(map(get_sanitised_payment, transaction_data.payments))
        print('payments: ', payments)

        data = {
            'txState': transaction_data.transaction_state,
            'payments': payments
        }
        print('data: ', data)
        return JSONResponse(status_code=200, content=jsonable_encoder(data), media_type='application/json')

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        return Response(status_code=status.HTTP_418_IM_A_TEAPOT)


# Webhooks
webhook_secret = os.environ.get("SERVER_WEBHOOK_SECRET")
webhook_handler = WebhookHandler(Environment.TEST, webhook_secret)


@app.post('/events')
async def events(request: Request):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - Event Webhook')

    agora_hmac_header = request.headers.get(AGORA_HMAC_HEADER)
    print('agora_hmac_header: ', agora_hmac_header)

    data = await request.body()
    print('data: ', data)
    decoded = data.decode('utf-8')
    print('decoded: ', decoded)

    status_code, request_body = webhook_handler.handle_events(
        _handle_events,
        agora_hmac_header,
        decoded,
    )
    # data.decode('utf-8'),

    print('request_body: ', request_body)
    print('status_code: ', status_code)

    return JSONResponse(status_code=status_code, content=request_body, media_type='application/json')


def _handle_events(received_events: List[Event]):
    for event in received_events:
        if not event.transaction_event:
            print(f'received event: {event}')
            continue

        transaction_id = base58.b58encode(event.transaction_event.tx_id)
        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)
        print('transaction completed')


@app.post('/sign_transaction')
async def sign_transaction(request: Request):
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - Sign Transaction Webhook')

    agora_hmac_header = request.headers.get(AGORA_HMAC_HEADER)
    print('agora_hmac_header: ', agora_hmac_header)

    data = await request.body()
    decoded = data.decode('utf-8')
    print('data: ', data)
    print('decoded: ', decoded)

    status_code, request_body = webhook_handler.handle_sign_transaction(
        _sign_transaction,
        agora_hmac_header,
        decoded,
    )
    print('status_code: ', status_code)
    print('request_body: ', request_body)

    return JSONResponse(status_code=status_code, content=request_body, media_type='application/json')


def _sign_transaction(req: SignTransactionRequest, resp: SignTransactionResponse):
    transaction_id = base58.b58encode(req.get_tx_id())
    transaction_id_string = transaction_id.decode("utf-8")
    print('transaction_id_string: ', transaction_id_string)

    if resp.rejected:
        print(
            f'transaction rejected: {transaction_id_string} ({len(req.payments)} payments)')
        return

    print(
        f'transaction approved: {transaction_id_string} ({len(req.payments)} payments)')

    # Note: This allows Agora to forward the transaction to the blockchain. However, it does not indicate that it will
    # be submitted successfully, or that the transaction will be successful. For example, the sender may have
    # insufficient funds.
    #
    # Backends may keep track of the transaction themselves using SignTransactionRequest.get_tx_hash() and rely on
    # either the Events webhook or polling to get the transaction status.
    resp.sign(app_hot_wallet)
    return


print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
