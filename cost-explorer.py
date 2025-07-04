# 관리가 필요한 link 계정의 lambda에 넣을 코드
import boto3
import json
from datetime import datetime, timedelta
import os

def lambda_handler(event, context):
    """
    Cost Explorer 데이터를 조회하여 S3에 저장하는 Lambda 함수
    """
    
    # AWS 클라이언트 초기화
    ce_client = boto3.client('ce', region_name='us-east-1')  # Cost Explorer는 us-east-1만 지원
    s3_client = boto3.client('s3')  # S3는 Lambda가 실행되는 리전 사용
    sts_client = boto3.client('sts')
    
    try:
        # 현재 계정 ID 가져오기
        account_id = sts_client.get_caller_identity()['Account']
        
        # S3 버킷 이름 (환경변수에서 가져오거나 직접 설정)
        bucket_name = os.environ.get('S3_BUCKET_NAME', f'cost-data-{account_id}')
        
        # 현재 월의 시작일과 종료일 설정
        current_date = datetime.now()
        start_date = current_date.replace(day=1).strftime('%Y-%m-%d')  # 이번 달 1일
        
        # 다음 달 1일을 종료일로 설정 (Cost Explorer는 end date 미포함)
        if current_date.month == 12:
            next_month = current_date.replace(year=current_date.year + 1, month=1, day=1)
        else:
            next_month = current_date.replace(month=current_date.month + 1, day=1)
        end_date = next_month.strftime('%Y-%m-%d')
        
        print(f"계정 {account_id}의 {current_date.strftime('%Y년 %m월')} 비용 데이터 조회 중... ({start_date} ~ {end_date})")
        
        # Cost Explorer API 호출 - 현재 월 비용 (서비스별)
        monthly_cost_response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='MONTHLY',
            Metrics=['BlendedCost'],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': 'SERVICE'
                }
            ]
        )
        
        # 데이터 구조화
        cost_data = {
            'account_id': account_id,
            'generated_at': datetime.now().isoformat(),
            'month': current_date.strftime('%Y-%m'),
            'monthly_costs': monthly_cost_response
        }
        
        # S3에 저장 - 타임스탬프 포함한 파일명
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        month_str = current_date.strftime('%Y%m')
        
        # 월별 데이터 저장 (타임스탬프 포함)
        monthly_key = f'cost-reports/monthly/{account_id}_{timestamp}.json'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=monthly_key,
            Body=json.dumps(cost_data, indent=2, default=str),
            ContentType='application/json'
        )
        
        print(f"비용 데이터 저장 완료: s3://{bucket_name}/{monthly_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'{current_date.strftime("%Y년 %m월")} 비용 데이터 수집 및 저장 완료',
                'account_id': account_id,
                'month': current_date.strftime('%Y-%m'),
                'file_created': monthly_key,
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': '비용 데이터 수집 실패'
            })
        }
