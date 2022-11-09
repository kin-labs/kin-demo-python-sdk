from flask_cors import CORS, cross_origin
from flask import Flask, request
from dotenv import load_dotenv
import json
import string
import os
from kinetic_sdk import KineticSdk, Keypair, TransactionType, Commitment


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
# app_hot_wallet = Keypair.from_mnemonic(
#     json.loads(os.environ.get('MNEMONIC')))

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
    }
    if kinetic_client_env == 'devnet':
        devnet_users.append(new_user)

    if kinetic_client_env == 'mainnet':
        mainnet_users.append(new_user)


def save_transaction(transaction: string):
    # TODO save your transaction data if required
    transactions.append(transaction)


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
        endpoint = os.environ.get(
            'KINETIC_ENDPOINT') or 'https://sandbox.kinetic.host'
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
                account=app_hot_wallet.public_key)
            if not balance['tokens']:
                raise Exception("No Token Account")

        except Exception as e:
            print('Error:', e)
            # if not, create it
            new_kinetic_client.create_account(
                owner=app_hot_wallet, commitment=Commitment('Finalized'))
            balance = new_kinetic_client.get_balance(
                account=app_hot_wallet.public_key)
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

        mnemonic = Keypair.generate_mnemonic()
        print('mnemonic: ', mnemonic)
        print(type(mnemonic))

        keypair = Keypair.from_mnemonic(mnemonic)
        # keypair = Keypair.random()
        print('keypair: ', keypair)

        commitment = Commitment('Finalized')
        print('commitment: ', commitment)

        account = kinetic_client.create_account(
            owner=keypair, commitment=commitment)

        print('Account created', keypair.public_key.to_base58().decode(),
              account['signature'])

        save_user(name, keypair)
        save_transaction(account['signature'])

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
        account_id = user['publicKey']
        print('account_id: ', account_id)

        balance = kinetic_client.get_balance(
            account=account_id)
        print('balance', balance)

        balance_in_kin = balance['balance']

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

        airdrop = kinetic_client.request_airdrop(
            account=account_id, amount=amount, commitment=Commitment('Finalized'))
        print('airdrop: ', airdrop)

        save_transaction(airdrop['signature'])

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

        transfer = kinetic_client.make_transfer(
            commitment=Commitment('Finalized'),
            amount=amount,
            destination=destination,
            owner=owner,
            tx_type=tx_type,
            reference_id='some id',
            reference_type='some reference',
            # sender_create=False
        )

        transaction_id = transfer['signature']
        print('transfer complete: ', transaction_id)

        save_transaction(transaction_id)

        response = '', 200

        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


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
        owner = from_user['keypair']
        print('sender: ', owner.public_key)

        payments = request.json.get('batch')
        print('payments: ', payments)

        destinations = []
        print('destinations: ', destinations)
        for payment in payments:
            to_user = get_user(payment["to"])
            destination = to_user["keypair"].public_key
            amount = payment['amount']
            destinations.append({'destination': destination, 'amount': amount})
        print('destinations: ', destinations)

        batch_transfer = kinetic_client.make_transfer_batch(
            commitment=Commitment('Finalized'),
            owner=owner,
            destinations=destinations,
            reference_id='some id',
            reference_type='some reference',
            # sender_create=False
        )

        transaction_id = batch_transfer['signature']
        print('batch transfer complete: ', transaction_id)

        save_transaction(transaction_id)

        response = '', 200

        return response

    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


@cross_origin()
@app.route('/transaction', methods=['GET'])
def transaction():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /transaction')

    try:
        transaction_id = request.args.get('transaction_id')
        print('transaction_id: ', transaction_id)

        transaction = kinetic_client.get_transaction(signature=transaction_id)
        print('transaction: ', transaction)

        response = str(transaction)
        return response
    except Exception as e:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print('Error:', e)
        response = '', 400
        return response


@cross_origin()
@app.route('/history', methods=['GET'])
def history():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - get /history')

    try:
        name = request.args.get('user')
        print('name', name)

        user = get_user(name)
        history = kinetic_client.get_history(
            account=user['keypair'].public_key)
        print('history', history)

        response = str(history)
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


@cross_origin()
@app.route('/events', methods=['POST'])
def events():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - Event Webhook')
    print('request: ', request.json)

    response = '', 200
    return response


@cross_origin()
@app.route('/verify', methods=["POST"])
def sign_transaction():
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    print(' - Verify Transaction Webhook')
    print('request: ', request.json)

    # TODO
    # Verify the transaction
    # Return 400 if no good
    # Return 200 to allow the transaction

    response = '', 200
    return response


print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')

port = os.environ.get('PORT') or 3001
if __name__ == '__main__':
    app.run(debug=True, port=port)
