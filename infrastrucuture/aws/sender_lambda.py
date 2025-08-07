import json
import boto3
import os
import urllib.parse
import time
import datetime

# Initialize AWS clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')
athena_client = boto3.client('athena')

def lambda_handler(event, context):
    """
    Simple sender Lambda - just embeds HTML and sends to subscribers
    """
    try:
        # Get newsletter path from query parameters
        query_params = event.get('queryStringParameters', {})
        if not query_params or 'newsletter' not in query_params:
            return create_response("Error: Missing newsletter parameter")
        
        newsletter_path = urllib.parse.unquote(query_params['newsletter'])
        print(f"Processing newsletter: {newsletter_path}")
        
        # Get HTML content from S3
        bucket_name = os.environ['NEWSLETTERS_BUCKET']
        response = s3_client.get_object(Bucket=bucket_name, Key=newsletter_path)
        html_content = response['Body'].read().decode('utf-8')
        
        # Get subscriber emails
        subscribers = get_subscribers()
        
        if not subscribers:
            return create_response("No subscribers found")
        
        # Send newsletter to all subscribers
        success_count = send_to_subscribers(html_content, subscribers)
        
        return create_response(f"Newsletter sent successfully to {success_count} subscribers!")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return create_response(f"Error: {str(e)}")


def get_subscribers():
    bucket = os.environ['SUBSCRIBERS_BUCKET']
    key    = 'subscribers.csv'

    body = s3_client.get_object(Bucket=bucket, Key=key)['Body'].read().decode('utf-8')

    subscribers = []
    for line in body.strip().splitlines():
        parts = [col.strip() for col in line.split(',')]
        email = parts[0]
        name  = parts[1] if len(parts) > 1 and parts[1] else email.split('@')[0]
        if email and '@' in email:
            subscribers.append({'email': email, 'name': name})
    return subscribers

def send_to_subscribers(html_content, subscribers):
    """
    Send HTML newsletter to all subscribers
    """
    from_email = os.environ['FROM_EMAIL']
    success_count = 0
    
    print(f"Sending to {len(subscribers)} subscribers")
    
    # Send in batches to avoid rate limits
    batch_size = 10
    for i in range(0, len(subscribers), batch_size):
        batch = subscribers[i:i + batch_size]
        
        for subscriber in batch:
            try:
                # Simple personalization - replace {{name}} if it exists
                personalized_html = html_content.replace('{{name}}', subscriber['name'])
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                ses_client.send_email(
                    Source=from_email,
                    Destination={'ToAddresses': [subscriber['email']]},
                    Message={
                        'Subject': {'Data': f"Omran's Agents Newsletter {timestamp}", 'Charset': 'UTF-8'},
                        'Body': {'Html': {'Data': personalized_html, 'Charset': 'UTF-8'}}
                    }
                )
                
                success_count += 1
                print(f"Sent to {subscriber['email']}")
                
            except Exception as e:
                print(f"Failed to send to {subscriber['email']}: {str(e)}")
        
        # Small delay between batches
        if i + batch_size < len(subscribers):
            time.sleep(1)
    
    return success_count

def create_response(message):
    """
    Create simple HTML response
    """
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/html'},
        'body': f"""
        <!DOCTYPE html>
        <html>
        <head><title>Newsletter Status</title></head>
        <body style="font-family: Arial, sans-serif; padding: 50px; text-align: center;">
            <h2>Newsletter Status</h2>
            <p style="font-size: 18px;">{message}</p>
        </body>
        </html>
        """
    }