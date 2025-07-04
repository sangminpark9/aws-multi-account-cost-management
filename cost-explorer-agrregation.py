# Payer 계정에서 lambda에 넣을 코드, 기능 : link 계정의 lambda로 만들어진 s3 버킷 조회 후 sns로 이메일 전달
import boto3
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import os

def lambda_handler(event, context):
    """
    6개 계정의 S3 버킷에서 비용 데이터를 가져와서 합산하고 SNS로 알림을 보내는 Lambda 함수
    """
    
    s3_client = boto3.client('s3')
    sns_client = boto3.client('sns')
    
    # SNS 토픽 ARN 설정
    SNS_TOPIC_ARN = 'arn:aws:sns:{region}:{payer-account-id}:{sns-topic-name}'
    
    # 6개 계정의 정보
    accounts = [
        {'account_id': '{linked-account-id-01}', 'alias': '{project-alias-01}', 'bucket': 'cost-data-{linked-account-id-01}'},
        {'account_id': '{linked-account-id-02}', 'alias': '{project-alias-02}', 'bucket': 'cost-data-{linked-account-id-02}'},
        {'account_id': '{linked-account-id-03}', 'alias': '{project-alias-03}', 'bucket': 'cost-data-{linked-account-id-03}'},
        {'account_id': '{linked-account-id-04}', 'alias': '{project-alias-04}', 'bucket': 'cost-data-{linked-account-id-04}'},
        {'account_id': '{linked-account-id-05}', 'alias': '{project-alias-05}', 'bucket': 'cost-data-{linked-account-id-05}'},
        {'account_id': '{linked-account-id-06}', 'alias': '{project-alias-06}', 'bucket': 'cost-data-{linked-account-id-06}'}
    ]
    
    # 한국 표준시 (UTC+9) 설정
    kst = timezone(timedelta(hours=9))
    current_time_kst = datetime.now(kst)
    
    # 현재 월 문자열 (예: 202407)
    current_month = current_time_kst.strftime('%Y%m')
    
    print(f"⏰ 리포트 생성 시간: {current_time_kst.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"=== {current_time_kst.strftime('%Y년 %m월')} AWS 비용 통합 리포트 ===")
    print(f"📅 생성시간: {current_time_kst.strftime('%Y-%m-%d %H:%M:%S KST')}")
    
    total_cost = Decimal('0')
    account_costs = {}
    service_costs = {}
    
    try:
        for account in accounts:
            account_id = account['account_id']
            account_alias = account['alias']
            bucket_name = account['bucket']
            
            try:
                print(f"\n📊 계정 {account_alias} ({account_id}) 데이터 조회 중...")
                
                # 해당 계정의 월별 폴더에서 최신 파일 찾기
                prefix = f'cost-reports/monthly/{account_id}_{current_month}'
                
                # S3에서 해당 prefix로 시작하는 파일들 나열
                list_response = s3_client.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=prefix
                )
                
                if 'Contents' not in list_response or len(list_response['Contents']) == 0:
                    raise Exception(f"No cost data files found for account {account_id}")
                
                # 최신 파일 찾기 (LastModified 기준)
                latest_file = max(list_response['Contents'], key=lambda x: x['LastModified'])
                object_key = latest_file['Key']
                
                print(f"   └─ 최신 파일: {object_key} (수정시간: {latest_file['LastModified']})")
                
                # 최신 파일 가져오기
                response = s3_client.get_object(
                    Bucket=bucket_name,
                    Key=object_key
                )
                
                # JSON 데이터 파싱
                cost_data = json.loads(response['Body'].read().decode('utf-8'))
                monthly_costs = cost_data.get('monthly_costs', {})
                
                account_total = Decimal('0')
                account_services = {}
                
                # 비용 데이터 처리
                if 'ResultsByTime' in monthly_costs:
                    for result in monthly_costs['ResultsByTime']:
                        if 'Groups' in result:
                            for group in result['Groups']:
                                service_name = group['Keys'][0] if group['Keys'] else 'Unknown'
                                amount = Decimal(group['Metrics']['BlendedCost']['Amount'])
                                
                                # 계정별 서비스 비용 합산
                                if service_name not in account_services:
                                    account_services[service_name] = Decimal('0')
                                account_services[service_name] += amount
                                
                                # 전체 서비스 비용 합산
                                if service_name not in service_costs:
                                    service_costs[service_name] = Decimal('0')
                                service_costs[service_name] += amount
                                
                                account_total += amount
                
                # 계정별 결과 저장
                account_costs[account_id] = {
                    'alias': account_alias,
                    'total': account_total,
                    'services': account_services
                }
                
                total_cost += account_total
                
                # 계정별 비용 출력
                print(f"✅ 계정 {account_alias} ({account_id}): ${account_total:.2f}")
                
                # 해당 계정의 주요 서비스 비용 출력 (상위 3개)
                sorted_services = sorted(account_services.items(), key=lambda x: x[1], reverse=True)[:3]
                for service, cost in sorted_services:
                    if cost > 0:
                        print(f"   └─ {service}: ${cost:.2f}")
                        
            except Exception as e:
                print(f"❌ 계정 {account_alias} ({account_id}) 데이터 조회 실패: {str(e)}")
                # 해당 계정 데이터가 없어도 계속 진행
                account_costs[account_id] = {
                    'alias': account_alias,
                    'total': Decimal('0'),
                    'services': {},
                    'error': str(e)
                }
        
        # 전체 결과 출력
        print(f"\n" + "="*50)
        print(f"💰 총 비용: ${total_cost:.2f}")
        print(f"📅 기준월: {current_time_kst.strftime('%Y년 %m월')}")
        print(f"🏢 계정 수: {len([acc for acc in account_costs.values() if acc['total'] > 0])}개")
        
        # 계정별 비용 순위
        print(f"\n📈 계정별 비용 순위:")
        sorted_accounts = sorted(account_costs.items(), key=lambda x: x[1]['total'], reverse=True)
        for i, (acc_id, data) in enumerate(sorted_accounts, 1):
            if data['total'] > 0:
                percentage = (data['total'] / total_cost * 100) if total_cost > 0 else 0
                print(f"{i}. 계정 {data['alias']} ({acc_id}): ${data['total']:,.2f} ({percentage:.1f}%)")
        
        # 서비스별 전체 비용 순위
        print(f"\n🔧 서비스별 비용 순위:")
        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (service, cost) in enumerate(sorted_services, 1):
            if cost > 0:
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                print(f"{i}. {service}: ${cost:,.2f} ({percentage:.1f}%)")
        
        # 결과 데이터 구성
        result_data = {
            'total_cost': float(total_cost),
            'month': current_month,
            'generated_at': current_time_kst.isoformat(),
            'timezone': 'KST (UTC+9)',
            'account_costs': {
                k: {
                    'alias': v['alias'],
                    'total': float(v['total']), 
                    'services': {sk: float(sv) for sk, sv in v['services'].items()}
                } for k, v in account_costs.items()
            },
            'service_costs': {k: float(v) for k, v in service_costs.items()},
            'summary': {
                'total_accounts': len(accounts),
                'active_accounts': len([acc for acc in account_costs.values() if acc['total'] > 0]),
                'top_service': max(service_costs.items(), key=lambda x: x[1])[0] if service_costs else 'None',
                'currency': 'USD'
            }
        }
        
        # SNS 메시지용 요약 정보 생성
        account_summary = []
        sorted_accounts = sorted(account_costs.items(), key=lambda x: x[1]['total'], reverse=True)
        for acc_id, data in sorted_accounts:
            if data['total'] > 0:
                percentage = (data['total'] / total_cost * 100) if total_cost > 0 else 0
                account_summary.append({
                    'account_id': acc_id,
                    'alias': data['alias'],
                    'cost': float(data['total']),
                    'percentage': round(percentage, 1),
                    'display_name': f"{data['alias']} ({acc_id})"
                })
        
        # 상위 서비스 정보
        top_services = []
        sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:5]
        for service, cost in sorted_services:
            if cost > 0:
                percentage = (cost / total_cost * 100) if total_cost > 0 else 0
                top_services.append({
                    'service': service,
                    'cost': float(cost),
                    'percentage': round(percentage, 1)
                })
        
        # SNS 메시지 생성 및 전송
        try:
            # 계정별 비용 요약 텍스트 생성
            account_text = ""
            for i, summary in enumerate(account_summary[:5], 1):  # 상위 5개 계정만
                account_text += f"\n{i}. {summary['alias']}: ${summary['cost']:,.2f} ({summary['percentage']}%)"
            
            # 서비스별 비용 요약 텍스트 생성
            service_text = ""
            for i, service in enumerate(top_services[:5], 1):  # 상위 5개 서비스만
                service_text += f"\n{i}. {service['service']}: ${service['cost']:,.2f} ({service['percentage']}%)"
            
            # SNS 메시지 본문 작성
            message_body = f"""
🔔 AWS 비용 리포트 알림

📅 기준월: {current_time_kst.strftime('%Y년 %m월')}
💰 총 비용: ${total_cost:,.2f}
🏢 활성 계정: {len(account_summary)}개
⏰ 생성시간: {current_time_kst.strftime('%Y-%m-%d %H:%M:%S KST')}

📊 계정별 비용 (상위 5개):{account_text}

🔧 서비스별 비용 (상위 5개):{service_text}

📈 상세 리포트는 Lambda 로그를 확인하세요.
            """.strip()
            
            # SNS 메시지 전송
            sns_response = sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message_body,
                Subject=f"AWS 비용 리포트 - {current_time_kst.strftime('%Y년 %m월')} (총 ${total_cost:,.2f})"
            )
            
            print(f"✅ SNS 이메일 발송 성공: {sns_response['MessageId']}")
            
        except Exception as sns_error:
            print(f"❌ SNS 이메일 발송 실패: {str(sns_error)}")
            # SNS 실패해도 전체 함수는 성공으로 처리
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': '비용 데이터 통합 완료',
                'total_cost': float(total_cost),
                'month': current_month,
                'generated_at': current_time_kst.strftime('%Y-%m-%d %H:%M:%S KST'),
                'account_summary': account_summary,
                'top_services': top_services,
                'summary': {
                    'total_accounts': len(accounts),
                    'active_accounts': len([acc for acc in account_costs.values() if acc['total'] > 0]),
                    'currency': 'USD'
                },
                'data': result_data
            }, default=str)
        }
        
    except Exception as e:
        print(f"❌ 전체 처리 중 오류 발생: {str(e)}")
        
        # 오류 발생 시에도 SNS 알림 전송
        try:
            error_message = f"""
🚨 AWS 비용 리포트 생성 실패

❌ 오류: {str(e)}
📅 시도 시간: {current_time_kst.strftime('%Y-%m-%d %H:%M:%S KST')}
🔍 Lambda 로그를 확인하여 상세 오류를 확인하세요.
            """.strip()
            
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=error_message,
                Subject=f"AWS 비용 리포트 생성 실패 - {current_time_kst.strftime('%Y-%m-%d %H:%M')}"
            )
            
            print(f"✅ 오류 SNS 알림 전송 완료")
            
        except Exception as sns_error:
            print(f"❌ 오류 SNS 알림 전송 실패: {str(sns_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': '비용 데이터 통합 실패'
            })
        }
