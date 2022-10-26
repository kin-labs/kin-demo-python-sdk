# from agora.webhook.sign_transaction import SignTransactionRequest, SignTransactionResponse
# from agora.webhook.handler import WebhookHandler, AGORA_HMAC_HEADER
# from agora.webhook.events import Event
# from agora.client import Client, Environment
# from agora.keys import PrivateKey, PublicKey
# from agora.model import Payment, TransactionType, Earn, EarnBatch
# from agora.utils import kin_to_quarks, quarks_to_kin
from flask_cors import CORS, cross_origin
from flask import Flask, request
from dotenv import load_dotenv
import json
from typing import List
import string
import os
from kinetic_sdk.kinetic_sdk import KineticSdk, Keypair, TransactionType
from kinetic_sdk_generated.model.commitment import Commitment


print('kinetic_sdk')


load_dotenv()

app = Flask(__name__)
CORS(app)

print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print(' - Kin Python SDK App')

app_index = int(os.environ.get('APP_INDEX'))
print(' - App Index', app_index)

kinetic_client = None
kinetic_client_env = 'devnet'

print(os.environ.get('BYTE_ARRAY'))
app_hot_wallet = Keypair.from_secret_key(
    json.loads(os.environ.get('BYTE_ARRAY')))

app_user_name = 'App'

app_public_key = app_hot_wallet.public_key.to_base58().decode()
print(' - App Public Key:', app_public_key)

app_user = {
    'name': app_user_name,
    'publicKey': app_public_key,
    'keypair': app_hot_wallet,
}

devnet_users = []
mainnet_users = []

transactions = list([])


def save_user(name: string, keypair: Keypair):
    # %%%%%%%%%%%% IMPORTANT %%%%%%%%%%%%
    # TODO - Save your account data securely
    new_user = {
        'name': name,
        'publicKey': keypair.public_key.to_base58().decode(),
        'keypair': keypair,
        # 'kinTokenAccounts': kin_token_accounts
    }
    if kinetic_client_env == 'devnet':
        devnet_users.append(new_user)

    if kinetic_client_env == 'mainnet':
        mainnet_users.append(new_user)


def save_transaction(transaction: string):
    # TODO save your transaction data if required
    transactions.append(transaction)


Sanitised_User_Data = {

}


def get_sanitised_user_data(user: string):
    name = user['name']
    print('name: ', name)
    public_key = user['publicKey']
    print('public_key: ', public_key)

    return {
        'name': name,
        'publicKey': public_key
    }


def get_user(name: string):
    user = None
    if kinetic_client_env == 'devnet' and devnet_users:
        user = next((x for x in devnet_users if x['name'] == name), None)
    if kinetic_client_env == 'mainnet' and mainnet_users:
        user = next((x for x in mainnet_users if x['name'] == name), None)
    if name == 'App':
        user = app_user
    return user


def get_users():
    print('get_users: ')
    users_response = []
    env = 1
    if kinetic_client_env == 'devnet':
        users_response = list(map(get_sanitised_user_data, devnet_users))

    if kinetic_client_env == 'mainnet':
        users_response = list(map(get_sanitised_user_data, mainnet_users))
        env = 0

    # insert app user into array
    users_response.insert(0, get_sanitised_user_data(app_user))

    return users_response, env


@cross_origin()
@app.route('/status', methods=['GET'])
def status():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /status')

    users_response, env = get_users()

    app_index_response = 0
    environment_response = 'devnet'
    if (kinetic_client is not None and hasattr(kinetic_client, 'config')):
        print('kinetic_client: ', kinetic_client.config)
        app_index_response = kinetic_client.config['index']
        environment_response = kinetic_client.config['environment']

    response = {'appIndex': app_index_response,
                'env': environment_response,
                'users': users_response,
                'transactions': transactions}

    return response


def reset_on_setup_error():
    global app_token_accounts
    app_token_accounts = []
    app_user['kinTokenAccounts'] = app_token_accounts

    global kinetic_client
    kinetic_client = None

    global kinetic_client_env
    kinetic_client_env = 'devnet'


@cross_origin()
@app.route('/setup', methods=['POST'])
def setup():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /setup')
    env_string = request.args.get('env')
    print('env_string', env_string)

    try:
        environment = 'devnet'
        endpoint = 'https://sandbox.kinetic.host'
        if env_string in ('Prod', 'Mainnet'):
            environment = 'mainnet'
            endpoint = os.environ.get('KINETIC_ENDPOINT')

        print('environment: ', environment)
        print('endpoint: ', endpoint)
        print('app_index: ', app_index)
        new_kinetic_client = KineticSdk.setup(
            endpoint=endpoint, environment=environment, index=app_index)
        print('new_kinetic_client: ', new_kinetic_client.config)

        balance = None
        try:
            # check it exists
            balance = new_kinetic_client.get_balance(
                app_hot_wallet.public_key.to_base58().decode())
        except Exception as e:
            print('Error:', e)
            # if not, create it
            new_kinetic_client.create_account(
                owner=app_hot_wallet, mint=new_kinetic_client.config['mint'])
            balance = new_kinetic_client.get_balance(
                app_hot_wallet.public_key.to_base58().decode())
        print('balance', balance)

        global kinetic_client
        kinetic_client = new_kinetic_client

        global kinetic_client_env
        kinetic_client_env = environment

        print('Setup successful')

        response = '', 200
        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        reset_on_setup_error()
        response = '', 400
        return response


@cross_origin()
@app.route('/account', methods=['POST'])
def account():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /account')

    try:
        name = request.args.get('name')
        print('name', name)

        keypair = Keypair.generate()

        print('kinetic_client.config: ', kinetic_client.config['mint'])
        print('Commitment: ', Commitment('Finalized'))

        kinetic_client.create_account(
            owner=keypair, mint=kinetic_client.config['mint'])

        print('Account created', keypair.public_key.to_base58().decode())

        save_user(name, keypair,)

        response = '', 201
        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


@cross_origin()
@app.route('/balance', methods=['GET'])
def balance():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /balance')

    try:
        name = request.args.get('user')
        print('name', name)

        user = get_user(name)
        balance = kinetic_client.get_balance(
            user['keypair'].public_key.to_base58().decode())
        print('balance', balance)

        balance_in_quarks = int(balance['balance'])
        balance_in_kin = balance_in_quarks / 100000

        response = str(balance_in_kin)

        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


@cross_origin()
@app.route('/airdrop', methods=['POST'])
def airdrop():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /airdrop')

    try:
        name = request.args.get('to')
        print('name', name)
        amount = request.args.get('amount')
        print('amount', amount)

        user = get_user(name)
        print('user: ', user)

        account_id = user['publicKey']
        print('account_id: ', account_id)

        transaction = kinetic_client.request_airdrop(
            account_id, amount, kinetic_client.config['mint'])
        print('transaction: ', transaction)

        save_transaction(transaction['signature'])

        response = '', 200

        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


def get_transaction_type(type_string):
    if type_string == 'P2P':
        return TransactionType.P2P
    if type_string == 'Earn':
        return TransactionType.EARN
    if type_string == 'Spend':
        return TransactionType.SPEND
    return TransactionType.NONE


@cross_origin()
@app.route('/send', methods=['POST'])
def send():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /send')

    try:
        from_name = request.json.get('from')
        print('from_name', from_name)
        to_name = request.json.get('to')
        print('to_name', to_name)
        amount = request.json.get('amount')
        print('amount', amount)
        type_string = request.json.get('type')
        print('type_string', type_string)

        owner = get_user(from_name)['keypair']
        print('owner: ', owner)
        destination = get_user(to_name)['publicKey']
        print('destination: ', destination)

        tx_type = get_transaction_type(type_string)
        print('tx_type: ', tx_type)

        transaction = kinetic_client.make_transfer(
            owner=owner, destination=destination, amount=amount, mint=kinetic_client.config['mint'], tx_type=tx_type)
        transaction_id = transaction['signature']
        print('transaction_id_string: ', transaction_id)

        save_transaction(transaction_id)

        response = '', 200

        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


def get_sanitised_batch_earn(payment):
    to_user = get_user(payment["to"])
    destination = to_user["keypair"].public_key
    amount = kin_to_quarks(payment["amount"])
    earn = Earn(destination, amount)
    return earn


@cross_origin()
@app.route('/earn_batch', methods=['POST'])
def earn_batch():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /earn_batch')

    try:
        from_name = request.json.get('from')
        print('from_name', from_name)
        from_user = get_user(from_name)
        sender = from_user['keypair']
        print('sender: ', sender.public_key.to_base58())

        payments = request.json.get('batch')
        print('payments: ', payments)
        earns = []
        for payment in payments:
            earns.append(get_sanitised_batch_earn(payment))
        batch = EarnBatch(sender, earns)

        batch_earn_result = kinetic_client.submit_earn_batch(batch)

        transaction_id = base58.b58encode(batch_earn_result.tx_id)
        transaction_id_string = transaction_id.decode("utf-8")
        print('Earn Batch Successful!: ', transaction_id_string)

        save_transaction(transaction_id_string)

        response = '', 200

        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


def get_sanitised_payment(payment):
    print('payment: ', payment)
    return {
        'type': payment.tx_type,
        'quarks': payment.quarks,
        'sender': payment.sender.to_base58(),
        'destination': payment.destination.to_base58(),
        'memo': str(payment.memo)
    }


@cross_origin()
@app.route('/transaction', methods=['GET'])
def transaction():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /transaction')

    try:
        transaction_id = request.args.get('transaction_id')
        print('transaction_id: ', transaction_id)

        decoded = base58.b58decode(transaction_id)
        transaction = kinetic_client.get_transaction(decoded)

        payments = list(map(get_sanitised_payment, transaction.payments))
        print('payments: ', payments)

        response = {
            'txState': transaction.transaction_state,
            'payments': payments
        }
        return response
    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


# Webhooks

# I use localtunnel for doing local development
# https://theboroer.github.io/localtunnel-www/

# You could also use ngrok
# https://ngrok.com/


# webhook_secret = os.environ.get("SERVER_WEBHOOK_SECRET")
# webhook_handler = WebhookHandler('devnet', webhook_secret)


# @cross_origin()
# @app.route('/events', methods=['POST'])
# def events():
#     print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
#     print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
#     print(' - Event Webhook')
#     status_code, request_body = webhook_handler.handle_events(
#         _handle_events,
#         request.headers.get(AGORA_HMAC_HEADER),
#         request.data.decode('utf-8'),
#     )
#     print('request_body: ', request_body)
#     print('status_code: ', status_code)
#     return request_body, status_code
# def _handle_events(received_events: List[Event]):
#     for event in received_events:
#         if not event.transaction_event:
#             print(f'received event: {event}')
#             continue
#         transaction_id = base58.b58encode(event.transaction_event.tx_id)
#         transaction_id_string = transaction_id.decode("utf-8")
#         print('transaction_id_string: ', transaction_id_string)
#         print('transaction completed')
# @cross_origin()
# @app.route('/sign_transaction', methods=["POST"])
# def sign_transaction():
#     print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
#     print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
#     print(' - Sign Transaction Webhook')
#     status_code, request_body = webhook_handler.handle_sign_transaction(
#         _sign_transaction,
#         request.headers.get(AGORA_HMAC_HEADER),
#         request.data.decode('utf-8'),
#     )
#     print('status_code: ', status_code)
#     print('request_body: ', request_body)
#     return request_body, status_code
# def _sign_transaction(req: SignTransactionRequest, resp: SignTransactionResponse):
#     transaction_id = base58.b58encode(req.get_tx_id())
#     transaction_id_string = transaction_id.decode("utf-8")
#     print('transaction_id_string: ', transaction_id_string)
#     # Note: Agora will _not_ forward a rejected transaction to the blockchain,
#     #       but it's safer to check that here as well.
#     if resp.rejected:
#         print(
#             f'transaction rejected: {transaction_id_string} ({len(req.payments)} payments)')
#         return
#     print(
#         f'transaction approved: {transaction_id_string} ({len(req.payments)} payments)')
#     # Note: This allows Agora to forward the transaction to the blockchain. However, it does not indicate that it will
#     # be submitted successfully, or that the transaction will be successful. For example, the sender may have
#     # insufficient funds.
#     #
#     # Backends may keep track of the transaction themselves using SignTransactionRequest.get_tx_hash() and rely on
#     # either the Events webhook or polling to get the transaction status.
#     resp.sign(app_hot_wallet)
#     return
print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')

port = os.environ.get('PORT') or 3001
if __name__ == '__main__':
    app.run(debug=True, port=port)
