import json
import boto3
import os
import urllib.parse

# Initialize AWS clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

def lambda_handler(event, context):
    """
    Simple approval Lambda - just embeds HTML with approval link
    """
    try:
        # Parse S3 event
        for record in event['Records']:
            bucket_name = record['s3']['bucket']['name']
            object_key = urllib.parse.unquote_plus(
                record['s3']['object']['key'], 
                encoding='utf-8'
            )
            
            print(f"Processing file: {object_key} from bucket: {bucket_name}")
            
            # Get HTML content from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            html_content = response['Body'].read().decode('utf-8')
            
            # Send approval email
            send_approval_email(object_key, html_content)
            
        return {
            'statusCode': 200,
            'body': json.dumps('Approval email sent successfully')
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

def send_approval_email(object_key, html_content):
    """
    Send approval email with embedded HTML and approval link
    """
    admin_email = os.environ['ADMIN_EMAIL']
    api_gateway_url = os.environ['API_GATEWAY_URL']
    from_email = os.environ['FROM_EMAIL']
    
    # Create approval link
    approval_link = f"{api_gateway_url}/approve?newsletter={urllib.parse.quote(object_key)}"
    
    # Create email with approval link above the HTML
    email_body = f"""
    <div style="background: #f0f0f0; padding: 20px; text-align: center; border: 2px solid #007cba; margin-bottom: 20px;">
        <h2 style="margin: 0; color: #007cba;">Newsletter Approval Required</h2>
        <p style="margin: 10px 0;">Review the newsletter below and click to approve:</p>
        <a href="{approval_link}" style="background: #28a745; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
            CLICK HERE TO APPROVE AND SEND
        </a>
    </div>
    
    {html_content}
    """
    
    # Send email
    ses_client.send_email(
        Source=from_email,
        Destination={'ToAddresses': [admin_email]},
        Message={
            'Subject': {'Data': 'Newsletter Approval Required', 'Charset': 'UTF-8'},
            'Body': {'Html': {'Data': email_body, 'Charset': 'UTF-8'}}
        }
    )
    
    print(f"Approval email sent to {admin_email}")