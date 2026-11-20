from os.path import exists
from os import environ
from string import Template

import plaid
from plaid.api import plaid_api
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_create_request_update import LinkTokenCreateRequestUpdate
from plaid.model.products import Products
from plaid.model.country_code import CountryCode

from flask import Flask
from flask import request
from flask import send_file
from dotenv import load_dotenv

load_dotenv()

PORT=environ['PORT_NUMBER']

def env_lookup():
    env = environ['PLAID_ENV']
    if env == 'sandbox':
        return plaid.Environment.Sandbox
    if env == 'development':
        return plaid.Environment.Development
    if env == 'production':
        return plaid.Environment.Production
    raise Exception('Expected one of [sandbox|development|production] as an environment.')

def init_client():
    configuration = plaid.Configuration(
        host=env_lookup(),
        api_key={
            'clientId': environ['PLAID_CLIENT_ID'],
            'secret': environ['PLAID_SECRET']
        }
    )
    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)

html_path = f"{environ.get('FINANCES_PATH')}/vendor/plaid2qif/manage-access-token"
client = init_client()
app = Flask('Plaid2QIF Account Updater')

@app.route("/api/create-link-token-update", methods=['POST'])
def create_link_token():
    access_token = read_access_token()
    # Create a one-time use link_token for the Item.
    # This link_token can be used to initialize Link
    # in update mode for the user.

    # Create a link_token for the given user
    kwargs = dict(
            client_name="Plaid2QIF Account Updater",
            country_codes=[CountryCode('US'), CountryCode('CA')],
            language='en',
            access_token = access_token,
            redirect_uri = environ['PLAID_SANDBOX_REDIRECT_URI'],
            user=LinkTokenCreateRequestUser(
                client_user_id='absent-user'
            )
        )
    # PLAID_ACCOUNT_SELECTION=1 makes Link show the account picker so new
    # accounts at the same institution can be added to this Item.
    if environ.get('PLAID_ACCOUNT_SELECTION') == '1':
        kwargs['update'] = LinkTokenCreateRequestUpdate(account_selection_enabled=True)
    # PLAID_CONSENT_PRODUCTS=investments asks the user to consent to products
    # the Item wasn't linked with (fixes ADDITIONAL_CONSENT_REQUIRED).
    consent = [p.strip() for p in environ.get('PLAID_CONSENT_PRODUCTS', '').split(',') if p.strip()]
    if consent:
        kwargs['additional_consented_products'] = [Products(p) for p in consent]
    request = LinkTokenCreateRequest(**kwargs)
    response = client.link_token_create(request)
    return response.to_dict()

@app.route("/mrr/fin", methods=['GET'])
def create_link():    
    template = f"{html_path}/update-token.html"
        
    with open(template, "r") as file:
        data = file.read()

    t = Template(data)
    return t.safe_substitute(access_token_storage=environ['ACCESS_TOKEN_FILE'])


@app.route('/icon.svg')
def icon():
    return send_file(f"{html_path}/icon.svg", mimetype='image/svg+xml')

def read_access_token():
  with open(environ.get('ACCESS_TOKEN_FILE')) as f:
    return f.readline().rstrip()

if __name__ == "__main__":
    app.run(port=PORT)
