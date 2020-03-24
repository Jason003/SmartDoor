import random
import time

import boto3
from boto3.dynamodb.conditions import Key

WP2_URL = 'https://cc-assignment2-frontend.s3-us-west-2.amazonaws.com/WP2.html'
db_resource = boto3.resource('dynamodb')
VISITOR_TABLE = 'cc-assn2-DB2-visitors'
PASSCODE_TABLE = 'cc-assn2-DB1-passcodes'
COLLECTION_ID = 'rekVideoBlog'
dynamodb = boto3.resource('dynamodb')


def lambda_handler(event, context):
    faceId = event['faceId']
    objectKey = event['objectKey']
    bucket = event['bucket']
    createdTimestamp = event['createdTimestamp']
    if event['name'] and event['phoneNumber'] and str(event['checked']):
        name = event['name']
        phoneNumber = event['phoneNumber']
        checked = event['checked']
        if int(checked) == 0:
            db_resource.Table(VISITOR_TABLE).put_item(
                Item={
                    'faceId': faceId,
                    'name': name,
                    'phoneNumber': phoneNumber,
                    'photos': [
                        {
                            'objectKey': str(objectKey) + '.jpg',
                            'bucket': bucket,
                            'createdTimestamp': str(createdTimestamp)
                        }
                    ]
                }
            )
            otp = generate_OTP()
            # send sms to visitor
            boto3.client("sns", region_name='us-west-2').publish(
                PhoneNumber='+1' + phoneNumber,
                Message='Hello, {}!\r\nYou are allowed to enter. Please click the following link and enter the OTP below:\r\n {}\r\nYour OTP is:\r\n {}\r\nThis OTP is valid in 5 minutes, and we may only send you a new OTP after 5 minutes'.format(
                    name, WP2_URL, otp)
            )
            db_resource.Table(PASSCODE_TABLE).put_item(
                Item={
                    'faceId': faceId,
                    'OTP': otp,
                    'timestamp': str(time.time()),
                    'expireTimestamp': str(time.time() + 300)
                }
            )
            return "Add visitor successfully!"
        else:
            deny_access([faceId], bucket, objectKey)
            return "Deny visitor\'s accesss successfully!"
    else:
        checked = event['checked']
        if int(checked) == 1:
            deny_access([faceId], bucket, objectKey)
            return "Deny visitor\'s accesss successfully!"
        else:
            return "Parameter error!"


def deny_access(faceIds, bucket, object_key):
    # delete face from collection
    boto3.client('rekognition').delete_faces(
        CollectionId=COLLECTION_ID,
        FaceIds=faceIds
    )
    # delete imgs from s3
    boto3.resource('s3').ObjectSummary(bucket, object_key).delete()


def search_OTP_dynamoDB(otp):
    table = dynamodb.Table(PASSCODE_TABLE)
    response = table.query(
        IndexName='OTP-index',
        KeyConditionExpression=Key('OTP').eq(otp)
    )
    return response['Items'] != []


def generate_OTP():
    otp = str(random.randint(100000, 999999))
    while search_OTP_dynamoDB(otp):
        otp = str(random.randint(100000, 999999))
    return otp
