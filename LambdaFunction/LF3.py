import time

import boto3
from boto3.dynamodb.conditions import Key

PASSCODE_TABLE = 'cc-assn2-DB1-passcodes'
VISITOR_TABLE = 'cc-assn2-DB2-visitors'
dynamodb = boto3.resource('dynamodb')
EXPIRE_TIME = 300


def lambda_handler(event, context):
    if event['OTP']:
        OTP = event['OTP']
        table = dynamodb.Table(PASSCODE_TABLE)
        response = table.query(
            IndexName='OTP-index',
            KeyConditionExpression=Key('OTP').eq(OTP)
        )
        item_array = response['Items']
        if item_array != []:
            record = item_array[0]
            faceId = record['faceId']
            timestamp = float(record['timestamp'])
            if float(time.time()) - timestamp <= EXPIRE_TIME:  # if not expired
                resp = dynamodb.Table(VISITOR_TABLE).query(KeyConditionExpression=Key('faceId').eq(faceId))
                name = resp['Items'][0]['name']
                return "Hi, " + name + "!\r\nYou enter the room successfully!"
            boto3.client('dynamodb').delete_item(  # if expired, delete otp from database
                Key={
                    'faceId': {
                        'S': faceId,
                    }
                },
                TableName=PASSCODE_TABLE
            )
        return "Permission denied!"
    else:
        return 'Parameter Error!'
