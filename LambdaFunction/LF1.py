import base64
import json
import random
import sys
import time
import uuid
from datetime import datetime

import boto3
import cv2
from boto3.dynamodb.conditions import Key

sys.path.insert(1, '/opt/')

S3_URL = 'https://cc-assignment2-b1.s3-us-west-2.amazonaws.com'
STREAM_ARN = 'arn:aws:kinesisvideo:us-west-2:710827020694:stream/LiveRekognitionVideoAnalysisBlog/1584299238155'
STREAM_NAME = 'LiveRekognitionVideoAnalysisBlog'
COLLECTION_ID = 'rekVideoBlog'
WP1_URL = 'https://cc-assignment2-frontend.s3-us-west-2.amazonaws.com/WP1.html'
WP2_URL = 'https://cc-assignment2-frontend.s3-us-west-2.amazonaws.com/WP2.html'
OWNER_EMAIL = 'jiefanli97@gmail.com'
BUCKET = 'cc-assignment2-b1'
VISITOR_TABLE = 'cc-assn2-DB2-visitors'
PASSCODE_TABLE = 'cc-assn2-DB1-passcodes'
EXPIRE_TIME = 300
dynamodb = boto3.resource('dynamodb')


def lambda_handler(event, context):
    records = event["Records"]
    decoded_data = json.loads(
        base64.b64decode(records[0]["kinesis"]["data"]).decode("utf-8")
    )
    fragment_number = decoded_data['InputInformation']['KinesisVideo']['FragmentNumber']

    if len(decoded_data['FaceSearchResponse']) == 0:
        # no face detected
        return

    face = decoded_data['FaceSearchResponse'][0]  # face that should be evaluated
    if len(face['MatchedFaces']) == 0 or face['MatchedFaces'][0]['Similarity'] < 10:
        # unknown face, should index the new face, save the image to s3 and send email to the owner
        inform_owner(fragment_number)
    else:  # indicates that face is known
        face_id = face['MatchedFaces'][0]['Face']['FaceId']
        # user has been authorized, and we have not sent OTP in last 5 minutes
        if find_faceId(face_id, VISITOR_TABLE) and (not find_faceId(face_id, PASSCODE_TABLE) or otp_expired(face_id)):
            otp = generate_OTP()  # generate otp for the user

            # add otp to PASSCODE_TABLE
            dynamodb.Table(PASSCODE_TABLE).put_item(
                Item={
                    'faceId': face_id,
                    'OTP': otp,
                    'timestamp': str(time.time()),
                    'expireTimestamp': str(time.time() + 300)
                }
            )

            # get visitor's information
            visitor = \
                dynamodb.Table(VISITOR_TABLE).query(KeyConditionExpression=Key('faceId').eq(face_id))['Items'][0]
            visitor_name, visitor_phone = visitor['name'], visitor['phoneNumber']

            # add new image to s3 bucket
            photo_filename = str(uuid.uuid1())
            photo_timestamp = str(datetime.now())
            visitor_img = get_img_bytes(fragment_number)

            boto3.client('s3').put_object(Body=visitor_img, Bucket=BUCKET,
                                          Key=photo_filename or str(uuid.uuid1()), ContentType='image/jpeg')

            # add the new photo to VISITOR_TABLE
            photos_array = dynamodb.Table(VISITOR_TABLE).get_item(
                Key={
                    'faceId': face_id
                }
            )['Item']['photos']  # original photo array

            photos_array.append(
                {'bucket': BUCKET, 'objectKey': photo_filename, 'createdTimestamp': photo_timestamp})

            dynamodb.Table(VISITOR_TABLE).update_item(
                Key={
                    'faceId': face_id
                },
                UpdateExpression="set photos=:a",
                ExpressionAttributeValues={
                    ':a': photos_array
                },
                ReturnValues="UPDATED_NEW"
            )

            # send sms to visitor
            boto3.client("sns", region_name='us-west-2').publish(
                PhoneNumber='+1' + str(visitor_phone),
                Message='Hello, {}!\r\nYou are allowed to enter. Please click the following link and enter the OTP below:\r\n {}\r\nYour OTP is:\r\n {}\r\nThis OTP is valid in 5 minutes, and we will only send you a new OTP after 5 minutes'.format(
                    visitor_name, WP2_URL, otp)
            )


def find_faceId(faceId, table_name):
    table = dynamodb.Table(table_name)
    response = table.query(KeyConditionExpression=Key('faceId').eq(faceId))
    item_array = response['Items']
    return len(item_array) > 0


def otp_expired(face_id):
    table_OTP = dynamodb.Table(PASSCODE_TABLE)
    response = table_OTP.query(KeyConditionExpression=Key('faceId').eq(face_id))
    item_array = response['Items']
    record = item_array[0]
    timestamp = float(record['timestamp'])
    return float(time.time()) - timestamp > EXPIRE_TIME


def inform_owner(fragment_number):
    visitor_img = get_img_bytes(fragment_number)
    rekognition_client = boto3.client('rekognition')
    response = rekognition_client.index_faces(
        CollectionId=COLLECTION_ID,
        Image={'Bytes': visitor_img},
        DetectionAttributes=['ALL'],
        MaxFaces=1,
        QualityFilter='AUTO'
    )
    faceId = response['FaceRecords'][0]['Face']['FaceId'] if response['FaceRecords'] else None
    if faceId:
        photo_filename = str(uuid.uuid1())
        # add new image to s3 bucket
        boto3.client('s3').put_object(Body=visitor_img, Bucket=BUCKET,
                                      Key=photo_filename or str(uuid.uuid1()), ContentType='image/jpeg')
        photo_timestamp = str(datetime.now())
        HTML = """
            <html>
            <head>
            </head>
            <body>
              <p>
              Hi,<br/>
              <br/>
              Smart Door has detected an unknown visitor, this is the photo:<br/></p>
              <div align="center">
              <img src=\"""" + S3_URL + '/' + photo_filename + """\", alt=\"jojo\" width="640px", height="480px"></div>
              <p>
              Click the following link to complete the registration.<br/></p>
              <br/>
              <a href=\"""" + WP1_URL + '#' + faceId + '&' + photo_filename + '&' + BUCKET + '&' + photo_timestamp + """"\">Smart Door Registration</a>
            </body>
            </html>
                        """
        SES_client = boto3.client('ses')
        SES_client.send_email(
            Source=OWNER_EMAIL,
            Destination={'ToAddresses': [OWNER_EMAIL, ]
                         },
            Message={
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': 'New Visitor'
                },
                'Body': {
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': 'It\'s only a test email!'
                    },
                    'Html': {
                        'Data': HTML,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )


def get_img_bytes(fragment_number):
    kinesis_client = boto3.client('kinesisvideo')
    response = kinesis_client.get_data_endpoint(
        StreamARN=STREAM_ARN,
        APIName='GET_MEDIA_FOR_FRAGMENT_LIST'
    )
    video_client = boto3.client('kinesis-video-archived-media',
                                endpoint_url=response['DataEndpoint']
                                )
    stream = video_client.get_media_for_fragment_list(
        StreamName=STREAM_NAME,
        Fragments=[
            fragment_number
        ]
    )
    chunk = stream['Payload'].read()
    with open('/tmp/stream.mkv', 'wb') as f:
        f.write(chunk)
    cap = cv2.VideoCapture('/tmp/stream.mkv')
    ret, frame = cap.read()
    _, buffer = cv2.imencode(".jpg", frame)
    cap.release()
    return buffer.tobytes()


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
