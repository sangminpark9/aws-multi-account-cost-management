# AWS Multi-Account Cost Management System

> 여러 AWS 계정의 비용을 자동으로 수집하고 통합하여 정기적으로 이메일 리포트를 제공하는 서버리스 비용 관리 시스템

## 📋 목차

- [개요](#개요)
- [아키텍처](#아키텍처)
- [주요 기능](#주요-기능)
- [시스템 구성](#시스템-구성)
- [배포 가이드](#배포-가이드)
- [사용법](#사용법)
- [모니터링](#모니터링)
- [비용 최적화](#비용-최적화)
- [문제 해결](#문제-해결)

## 개요

이 프로젝트는 AWS Organizations 환경에서 Payer 계정이 여러 링크 계정의 비용을 효율적으로 관리할 수 있도록 설계된 자동화 시스템입니다. 각 계정의 비용 데이터를 개별적으로 수집하고, 이를 통합하여 정기적으로 이메일 리포트를 발송합니다.

### 주요 특징

- 🔄 **자동화된 비용 수집**: EventBridge 스케줄러를 통한 정기적 실행
- 📊 **통합 리포트**: 여러 계정의 비용을 한 번에 확인
- 📧 **이메일 알림**: SNS를 통한 자동 리포트 발송
- 🛡️ **안정성**: 개별 계정 오류 시에도 전체 프로세스 계속 진행
- 💰 **비용 효율성**: 서버리스 아키텍처로 운영 비용 최소화

## 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Link Account  │    │   Link Account  │    │   Link Account  │
│       #1        │    │       #2        │    │      #3...      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Lambda Function │    │ Lambda Function │    │ Lambda Function │
│cost-explorer.py │    │cost-explorer.py │    │cost-explorer.py │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   S3 Bucket     │    │   S3 Bucket     │    │   S3 Bucket     │
│ cost-data-xxx   │    │ cost-data-xxx   │    │ cost-data-xxx   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     Payer Account       │
                    │                         │
                    │ ┌─────────────────────┐ │
                    │ │ Lambda Function     │ │
                    │ │ cost-explorer-      │ │
                    │ │ aggregation.py      │ │
                    │ └─────────────────────┘ │
                    │           │             │
                    │           ▼             │
                    │ ┌─────────────────────┐ │
                    │ │    SNS Topic        │ │
                    │ │   Email Alerts      │ │
                    │ └─────────────────────┘ │
                    └─────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │   Email Recipients      │
                    │    (Team Members)       │
                    └─────────────────────────┘
```

## 주요 기능

### 비용 데이터 수집
- Cost Explorer API를 통한 실시간 비용 데이터 조회
- 서비스별 비용 분석
- 현재 월 기준 비용 추적

### 데이터 통합 및 분석
- 다중 계정 비용 데이터 통합
- 계정별 비용 순위 생성
- 서비스별 비용 분석
- 비용 비율 계산

### 자동화된 리포트
- 정기적 이메일 알림 (하루 2회)
- 상세 비용 분석 리포트
- 오류 발생 시 즉시 알림

## 시스템 구성

### 1. 데이터 수집 계층 (각 링크 계정)
- **Lambda 함수**: `cost-explorer.py`
- **S3 버킷**: `cost-data-{account-id}`
- **EventBridge**: 스케줄 기반 실행 트리거

### 2. 데이터 통합 계층 (Payer 계정)
- **Lambda 함수**: `cost-explorer-aggregation.py`
- **SNS 토픽**: 이메일 알림 발송
- **EventBridge**: 통합 처리 스케줄

### 3. 스케줄링
- **실행 시간**: 매일 12:00, 18:00 (KST)
- **Cron 표현식**: `0 3,9 * * ? *` (UTC 기준)

## 배포 가이드

### 사전 요구사항
- AWS Organizations 환경
- Payer 계정과 링크 계정 간 적절한 IAM 권한 설정
- Cost Explorer 활성화

### 1. 링크 계정 설정

각 링크 계정에서 다음 리소스를 생성합니다:

#### S3 버킷
```bash
aws s3 mb s3://cost-data-{account-id}
```

#### Lambda 함수
- 함수명: `cost-explorer-{account-id}`
- 런타임: Python 3.9+
- 메모리: 128MB
- 타임아웃: 5분

#### EventBridge 규칙
```bash
aws events put-rule --name "cost-collection-schedule" \
  --schedule-expression "cron(0 3,9 * * ? *)"
```

### 2. Payer 계정 설정

#### SNS 토픽
```bash
aws sns create-topic --name aws-cost-reports
```

#### 이메일 구독
```bash
aws sns subscribe --topic-arn arn:aws:sns:region:account:aws-cost-reports \
  --protocol email --notification-endpoint your-email@example.com
```

#### Lambda 함수
- 함수명: `cost-explorer-aggregation`
- 런타임: Python 3.9+
- 메모리: 512MB
- 타임아웃: 15분

### 3. 권한 설정

#### Lambda 실행 역할 (링크 계정)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetUsageReport"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::cost-data-{account-id}/*"
    }
  ]
}
```

#### Lambda 실행 역할 (Payer 계정)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::cost-data-*",
        "arn:aws:s3:::cost-data-*/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:region:account:aws-cost-reports"
    }
  ]
}
```

## 사용법

### 시스템 배포 후
1. 모든 링크 계정에서 Lambda 함수가 정상적으로 실행되는지 확인
2. Payer 계정에서 통합 Lambda 함수 테스트 실행
3. 이메일 알림 수신 확인

### 리포트 내용
이메일 리포트에는 다음 정보가 포함됩니다:
- 총 비용 및 기준 월
- 계정별 비용 순위 (상위 5개)
- 서비스별 비용 순위 (상위 5개)
- 각 항목별 비용 비율

### 예시 리포트
```
🔔 AWS 비용 리포트 알림

📅 기준월: 2024년 07월
💰 총 비용: $1,234.56
🏢 활성 계정: 6개
⏰ 생성시간: 2024-07-04 18:00:00 KST

📊 계정별 비용 (상위 5개):
1. ProjectA: $456.78 (37.0%)
2. ProjectB: $234.56 (19.0%)
3. ProjectC: $123.45 (10.0%)
...

🔧 서비스별 비용 (상위 5개):
1. Amazon EC2: $345.67 (28.0%)
2. Amazon S3: $234.56 (19.0%)
3. Amazon RDS: $123.45 (10.0%)
...
```

## 모니터링

### CloudWatch 메트릭
- Lambda 함수 실행 상태
- 오류 발생 횟수
- 실행 시간 추적

### 로그 분석
- CloudWatch Logs에서 상세 실행 로그 확인
- 오류 발생 시 즉시 SNS 알림

### 알림 설정
- 성공적인 리포트 생성 알림
- 오류 발생 시 즉시 알림
- 개별 계정 데이터 수집 실패 알림

## 비용 최적화

### 예상 비용 (월간)
- **Lambda 실행**: $1-5 (실행 횟수에 따라)
- **S3 저장소**: $1-3 (데이터 크기에 따라)
- **Cost Explorer API**: $10-20 (호출 횟수에 따라)
- **SNS 알림**: $1 미만
- **총 예상 비용**: $15-30/월

### 비용 절감 방안
- S3 라이프사이클 정책으로 오래된 데이터 삭제
- Lambda 함수 실행 시간 최적화
- 필요에 따라 스케줄 조정

## 문제 해결

### 일반적인 문제

#### 1. Cost Explorer API 오류
```
해결방법: Cost Explorer는 us-east-1 리전에서만 사용 가능
Lambda 함수의 Cost Explorer 클라이언트를 us-east-1로 설정
```

#### 2. Cross-Account 접근 오류
```
해결방법: S3 버킷 정책과 IAM 역할 권한 재확인
Payer 계정의 역할이 링크 계정의 S3 버킷에 접근 가능한지 확인
```

#### 3. 이메일 알림 미수신
```
해결방법: SNS 구독 상태 확인
이메일 주소의 구독 확인 메일 처리 여부 확인
```

### 디버깅 가이드
1. CloudWatch Logs 그룹에서 Lambda 함수 로그 확인
2. S3 버킷에 데이터 파일이 생성되는지 확인
3. SNS 토픽의 구독 상태 확인
4. EventBridge 규칙의 활성화 상태 확인

## 확장 가능성

### 추가 기능
- 📊 **CloudWatch 대시보드**: 실시간 비용 모니터링
- 🚨 **비용 임계값 알림**: 설정된 비용 한도 초과 시 알림
- 📈 **비용 예측**: 과거 데이터 기반 비용 예측
- 💬 **Slack/Teams 연동**: 다양한 알림 채널 지원
- 🎯 **태그 기반 분석**: 리소스 태그별 비용 분석

### 아키텍처 개선
- DynamoDB를 활용한 히스토리 데이터 관리
- API Gateway를 통한 웹 대시보드 제공
- CloudFormation/CDK를 활용한 자동화된 배포

### 개발 환경 설정
```bash
# 프로젝트 클론
git clone https://github.com/your-org/aws-multi-account-cost-management.git

# 의존성 설치
pip install -r requirements.txt

# 로컬 테스트
python -m pytest tests/
```

**📝 참고**: 이 시스템은 AWS Organizations 환경에서 최적화되어 있으며, 개별 AWS 계정 환경에서는 수정이 필요할 수 있습니다.
