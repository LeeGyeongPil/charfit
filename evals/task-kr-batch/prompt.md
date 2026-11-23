---
name: task-kr-batch
max_turns: 16
---

notices.jsonl 에 알림 문자 템플릿이 한 줄에 하나씩(JSON) 들어 있어. 우리 게이트웨이는 엄격 EUC-KR(KS X 1001)만 보내고, 90바이트까지는 SMS, 2,000바이트까지는 LMS로 나가고, 인코딩이 안 되는 글자가 하나라도 있으면 발송 실패야. 이 템플릿들 중 SMS, LMS, 발송 실패가 각각 몇 개야?
