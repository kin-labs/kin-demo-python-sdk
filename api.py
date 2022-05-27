import os
import string
from typing import List

from dotenv import load_dotenv
from flask import Flask, request
from flask_cors import CORS, cross_origin
import base58

from agora.utils import kin_to_quarks, quarks_to_kin
from agora.model import Payment, TransactionType, Earn, EarnBatch
from agora.keys import PrivateKey, PublicKey
from agora.client import Client, Environment

from agora.webhook.events import Event
from agora.webhook.handler import WebhookHandler, AGORA_HMAC_HEADER
from agora.webhook.sign_transaction import SignTransactionRequest, SignTransactionResponse

load_dotenv()

app = Flask(__name__)
CORS(app)

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
    # %%%%%%%%%%%% IMPORTANT %%%%%%%%%%%%
    # TODO - Save your account data securely
    new_user = {
        'name': name,
        'publicKey': private_key.public_key.to_base58(),
        'privateKey': private_key,
        'kinTokenAccounts': kin_token_accounts
    }
    if kin_client_env == Environment.TEST:
        test_users.append(new_user)

    if kin_client_env == Environment.PRODUCTION:
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
    return user


def get_users():
    users_response = []
    env = 1
    if kin_client_env == Environment.TEST:
        users_response = list(map(get_sanitised_user_data, test_users))

    if kin_client_env == Environment.PRODUCTION:
        users_response = list(map(get_sanitised_user_data, prod_users))
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
    print('kin_client_env', kin_client_env)
    print('kin_client', kin_client)

    users_response, env = get_users()

    app_index_response = 0
    if(hasattr(kin_client, '_app_index')):
        app_index_response = kin_client._app_index

    response = {'appIndex': app_index_response,
                'env': env,
                'users': users_response,
                'transactions': transactions}

    return response


def reset_on_setup_error():
    global app_token_accounts
    app_token_accounts = []
    app_user['kinTokenAccounts'] = app_token_accounts

    global kin_client
    kin_client = None

    global kin_client_env
    kin_client_env = Environment.TEST


@cross_origin()
@app.route('/setup', methods=['POST'])
def setup():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - post /setup')
    env_string = request.args.get('env')
    print('env_string', env_string)

    try:
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
        kin_client_env = env

        # Webhooks - Update webhook handler if env changes
        global webhook_handler
        webhook_handler = WebhookHandler(kin_client_env, webhook_secret)

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

        private_key = PrivateKey.random()

        kin_client.create_account(private_key)
        kin_token_accounts = kin_client.resolve_token_accounts(
            private_key.public_key)

        print('Account created', private_key.public_key.to_base58())

        save_user(name, private_key, kin_token_accounts)

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
        balance = kin_client.get_balance(user['privateKey'].public_key)
        print('balance', balance)

        balance_in_kin = quarks_to_kin(balance)
        print('balance_in_kin', balance_in_kin)

        response = balance_in_kin

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

        quarks = kin_to_quarks(amount)
        print('quarks: ', quarks)

        user = get_user(name)
        token_account = user['kinTokenAccounts'][0]
        print('token_account: ', token_account.to_base58())

        transaction = kin_client.request_airdrop(
            token_account, quarks)

        transaction_id = base58.b58encode(transaction)
        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)

        save_transaction(transaction_id_string)

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

        from_user = get_user(from_name)
        to_user = get_user(to_name)

        sender = from_user['privateKey']
        print('sender: ', sender.public_key.to_base58())

        destination = to_user["privateKey"].public_key
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
    destination = to_user["privateKey"].public_key
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
        sender = from_user['privateKey']
        print('sender: ', sender.public_key.to_base58())

        payments = request.json.get('batch')
        print('payments: ', payments)
        earns = []
        for payment in payments:
            earns.append(get_sanitised_batch_earn(payment))
        batch = EarnBatch(sender, earns)

        batch_earn_result = kin_client.submit_earn_batch(batch)

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
        transaction = kin_client.get_transaction(decoded)

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
webhook_secret = os.environ.get("SERVER_WEBHOOK_SECRET")
webhook_handler = WebhookHandler(Environment.TEST, webhook_secret)


@cross_origin()
@app.route('/events', methods=['POST'])
def events():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - Event Webhook')

    status_code, request_body = webhook_handler.handle_events(
        _handle_events,
        request.headers.get(AGORA_HMAC_HEADER),
        request.data.decode('utf-8'),
    )

    print('request_body: ', request_body)
    print('status_code: ', status_code)
    return request_body, status_code


def _handle_events(received_events: List[Event]):
    for event in received_events:
        if not event.transaction_event:
            print(f'received event: {event}')
            continue

        transaction_id = base58.b58encode(event.transaction_event.tx_id)
        transaction_id_string = transaction_id.decode("utf-8")
        print('transaction_id_string: ', transaction_id_string)
        print('transaction completed')


@cross_origin()
@app.route('/sign_transaction', methods=["POST"])
def sign_transaction():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - Sign Transaction Webhook')

    status_code, request_body = webhook_handler.handle_sign_transaction(
        _sign_transaction,
        request.headers.get(AGORA_HMAC_HEADER),
        request.data.decode('utf-8'),
    )
    print('status_code: ', status_code)
    print('request_body: ', request_body)

    return request_body, status_code


def _sign_transaction(req: SignTransactionRequest, resp: SignTransactionResponse):
    transaction_id = base58.b58encode(req.get_tx_id())
    transaction_id_string = transaction_id.decode("utf-8")
    print('transaction_id_string: ', transaction_id_string)

    # Note: Agora will _not_ forward a rejected transaction to the blockchain,
    #       but it's safer to check that here as well.
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

port = os.environ.get('PORT') or 3001
if __name__ == '__main__':
    app.run(debug=True, port=port)
