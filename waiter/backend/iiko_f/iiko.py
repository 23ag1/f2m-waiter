import requests

# from database.db import Database  # REMOVED: SQLite legacy, migrated to PostgreSQL

korean_chick_iiko_portion = {'Крылья': ["3 шт", "6 шт", "9шт"],
                             'Чикен попкорн': ["100 гр", "200 гр", "300 гр"],
                             'Чикен Сет': ["Малый", "Средний", "Большой"],
                             'Кимчи': ["50 гр", "150 гр"],
                             'Огурцы битые': ["50 гр", "150 гр"],
                             'Спаржа по-корейски': ["50 гр", "150 гр"],
                             'Морковь по-корейски': ["50 гр", "150 гр"],
                             'Маринованный дайкон': ["50 гр", "150 гр"],
                             'Данмудзи': ["50 гр", "150 гр"]}
korean_chick_iiko_id = {'Крылья 3 шт': '08801600-8203-4f91-86bf-cc7eb4c14961',
                        'Крылья 6 шт': 'c33645f8-e9a8-426a-83e4-0c859ff3464a',
                        'Крылья 9 шт': '9b85257f-979d-4d44-a6a3-cd6ce546341e',
                        'Чикен попкорн 100 гр': '6b368d2b-534a-48e5-bc1d-3d64b67336ed',
                        'Чикен попкорн 200 гр': 'ce54e6ca-eac6-4f9f-bb60-21c5379fd698',
                        'Чикен попкорн 300 гр': '426f9e6d-6e07-4c6e-8617-ffbd940dd118',
                        'Чикен Сет Малый': "96a1bc92-dc77-4e72-a3dc-ff9c66623ece",
                        'Чикен Сет Средний': "ac8f13d5-0cbe-41fb-a887-18bd24d4e96b",
                        'Чикен Сет Большой': "af4145fb-46e4-4b32-ac51-d549be11c3fb",
                        'Огурцы битые 50 гр': "e7393e40-5b2e-4f48-a43f-5170a7f5841e",
                        'Огурцы битые 150 гр': "fb06382d-3f1b-43ce-904c-b54ee7e5815b",
                        'Кимчи 50 гр': "5d887f89-52d9-4ec8-babe-d2dbe3f50496",
                        'Кимчи 150 гр': "347c478a-6728-4d07-be89-345c31d3870a",
                        'Спаржа по-корейски 50 гр': "40054143-f17f-4ab3-86f7-e5bb519d5d4f",
                        'Спаржа по-корейски 150 гр': "cbf2f32c-b4d0-48cc-b01e-51a59321151c",
                        'Морковь по-корейски 50 гр': "6bd6973e-4d71-43a9-b3df-4707576112ed",
                        'Морковь по-корейски 150 гр': "bbdb0f76-adb3-4e64-8915-70d8f4200544",
                        'Маринованный дайкон 50 гр': "d3d91a8d-9874-4eb1-a04f-a9dd39521053",
                        'Маринованный дайкон 150 гр': "cf111fe0-65ac-4cba-a6f7-bc55ef196207",
                        'Данмудзи 50 гр': "9b224d03-36da-4fe9-83d3-fa6a55f9cad8",
                        'Данмудзи 150 гр': "6453bfe8-d36b-4c7b-b034-217ee9a67099",
                        }

korean_chick_portion_price_range = {'Крылья': '347-797',
                                    'Чикен попкорн': '347-747',
                                    'Чикен Сет': '497-1477',
                                    'Кимчи': '127-277',
                                    'Огурцы битые': '127-277',
                                    'Спаржа по-корейски': '127-277',
                                    'Морковь по-корейски': '127-277',
                                    'Маринованный дайкон': '127-277',
                                    'Данмудзи': '127-277'}

korean_chick_portion_price = {'Крылья 3 шт': '347',
                              'Крылья 6 шт': '597',
                              'Крылья 9 шт': '797',
                              'Чикен попкорн 100 гр': '347',
                              'Чикен попкорн 200 гр': '547',
                              'Чикен попкорн 300 гр': '747',
                              'Чикен Сет Малый': '497',
                              'Чикен Сет Средний': '977',
                              'Чикен Сет Большой': '1477',
                              'Огурцы битые 50 гр': '127',
                              'Огурцы битые 150 гр': '277',
                              'Кимчи 50 гр': '127',
                              'Кимчи 150 гр': '277',
                              'Спаржа по-корейски 50 гр': '127',
                              'Спаржа по-корейски 150 гр': '277',
                              'Морковь по-корейски 50 гр': '127',
                              'Морковь по-корейски 150 гр': '277',
                              'Маринованный дайкон 50 гр': '127',
                              'Маринованный дайкон 150 гр': '277',
                              'Данмудзи 50 гр': '127',
                              'Данмудзи 150 гр': '277',
                              }
API_KEYS = {'Korean Chick Водный стадион': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Кунцевская': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Медведково': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Красногорск': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Октябрьское поле': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Первомайская': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Раменки': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Бауманская': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Митино': '932a68a1356541cda65afb9245e8bc3b',
            'Korean Chick Вешняковская': '932a68a1356541cda65afb9245e8bc3b'}
BASE_URL = "https://api-ru.iiko.services/api/1/"

name_and_iiko_name = {'Korean Chick Водный стадион': 'Korean Chick (Водный стадион)',
                      'Korean Chick Кунцевская': 'Korean Chick (Кунцевская)',
                      'Korean Chick Медведково': 'Korean Chick (Медведково)',
                      'Korean Chick Красногорск': 'Korean Chick (Красногорск)',
                      'Korean Chick Октябрьское поле': 'Korean Chick (Октябрьское поле)',
                      'Korean Chick Первомайская': 'Korean Chick (Первомайская)',
                      'Korean Chick Раменки': 'Korean Chick (Раменки)',
                      'Korean Chick Бауманская': 'Korean Chick (Бауманская)',
                      'Korean Chick Митино': 'Korean Chick (Митино)',
                      'Korean Chick Вешняковская': 'Korean Chick (Вешняковская)',
                      'Prime Hill': 'Мой ресторан'}

name_and_iiko_id = {'Korean Chick (Вешняковская)': '0c176f22-c5c0-4952-9b21-eb0b13debfc4',
                    'Korean Chick (Кунцевская)': '23ff922c-4fbd-4837-85f4-c5a6ff8167a9',
                    'Korean Chick (Медведково)': '29f2c38c-ea93-47a2-9789-050929a5e470',
                    'Korean Chick (Водный стадион)': '5010d347-1922-4587-8d4f-cd5dc6a04263',
                    'Korean Chick (Красногорск)': '5029ee3e-aec2-4cb8-a148-9f5e1102b4fa',
                    'Korean Chick (Октябрьское поле)': '784467af-f196-4b11-8e5e-cec2dfcfee8e',
                    'Korean Chick (Первомайская)': '8f637e7a-c8c0-4ac7-8771-0fdc7d163bbb',
                    'Korean Chick (Раменки)': 'bba48376-5731-4ac3-a87a-f0924017fb06',
                    'Korean Chick (Бауманская)': 'bf311dde-6bf0-4bbe-ad96-751e39a1e556',
                    'Korean Chick (Митино)': 'ea9c03f3-e35f-49e4-ae3e-21d0c6c44922',
                    'Мой ресторан': 'b65000f0-2349-4c52-91bf-42baf403276f'}

name_and_terminal_id = {'Korean Chick (Вешняковская)': 'f8ce9c36-b709-4434-9403-871739e5862b',
                        'Korean Chick (Кунцевская)': 'ea018463-fc8e-4633-834b-dff3fd288049',
                        'Korean Chick (Медведково)': 'e272f1d7-49f7-4641-9c24-4c3a6e5cf414',
                        'Korean Chick (Водный стадион)': 'af3eb7e1-d916-42da-8ac9-e2736ed3713c',
                        'Korean Chick (Красногорск)': 'd2e58e32-0e03-4345-84f8-01bbcf18d9fc',
                        'Korean Chick (Октябрьское поле)': '673adb26-ce75-40c8-a031-8d1f8d6fda65',
                        'Korean Chick (Первомайская)': 'ffb788ae-6858-42a9-837f-74f31697c7f8',
                        'Korean Chick (Раменки)': 'ee38195b-c173-4d1c-9ee6-11d701b5c63c',
                        'Korean Chick (Бауманская)': '897fb0ec-b81b-bf20-0171-6f25d2ba00cd',
                        'Korean Chick (Митино)': 'cb3dcc7a-cf3d-4f64-9280-5589ddf3a593',
                        'Мой ресторан': '083ee2e6-b9ad-236f-0178-b2d0329300ce'}


def get_organizations(access_token):
    url = f"{BASE_URL}organizations"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("organizations", [])


def find_terminals(access_token, organization_id):
    url = f"{BASE_URL}terminal_groups"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "organizationIds": [organization_id],
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def add_order(access_token, organization_id, terminal, items):
    url = f"{BASE_URL}order/create"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "organizationId": organization_id,
        "terminalGroupId": terminal,
        "order": {
            'items': items
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    print(response.text)
    return response.json()


def get_all_tables(access_token, terminal_id):
    url = f"{BASE_URL}reserve/available_restaurant_sections"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "terminalGroupIds": [
            f"{terminal_id}"
        ]}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()['restaurantSections']['tables']


test_answer = {
    "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
    "number": 0,
    "name": "string",
    "seatingCapacity": 0,
    "revision": 0,
    "isDeleted": True,
    "posId": "7f542382-3a91-4db8-938e-e9f86b88057c"
}


def get_curr_orders_by_table(access_token, organization_id, table):
    url = f"{BASE_URL}order/by_table"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "organizationIds": [
            f"{organization_id}"],
        "tableIds": [
            f"{table}"]}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()['orders']


test_answer_2 = {
    "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
    "posId": "7f542382-3a91-4db8-938e-e9f86b88057c",
    "externalNumber": "string",
    "organizationId": "7bc05553-4b68-44e8-b7bc-37be63c6d9e9",
    "timestamp": 0,
    "creationStatus": "Success",
    "errorInfo": {},
    "order": {}
}


def edit_order(access_token, organization_id, terminal, items):
    url = f"{BASE_URL}order/add+items"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "organizationId": organization_id,
        "terminalGroupId": terminal,
        "order": {
            'items': items
        }
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()
