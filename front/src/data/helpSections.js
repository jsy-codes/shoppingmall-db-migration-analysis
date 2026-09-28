// ─── 도움말 데이터 ─────────────────────────────────────────────
const HELP_SECTIONS = [
  {
    icon: '❓',
    title: '이 페이지는 무엇인가요?',
    desc: 'Oracle DB를 MySQL로 이관할 때 발생할 수 있는 위험 패턴을 자동으로 분석하는 AI 진단 도구입니다. SQL을 입력하면 이관 실패 가능성, 위험도 점수, 수정 DDL을 즉시 제공합니다.',
  },
  {
    icon: '✍️',
    title: 'SQL 입력 방법',
    desc: '분석할 Oracle SQL을 직접 입력하거나 .sql 이나 .txt 파일을 업로드하세요. 여러 쿼리를 한 번에 분석하려면 세미콜론(;)으로 구분합니다.',
    example: {
      label: '입력 예시',
      code: `SELECT * FROM orders WHERE ROWNUM <= 10;\nSELECT NVL(customer_name, '미입력') FROM customers;\nSELECT employee_id FROM emp CONNECT BY PRIOR employee_id = manager_id`,
    },
  },
  {
    icon: '📊',
    title: '배치 분석 요약 카드',
    desc: '여러 쿼리를 분석했을 때 전체 결과를 한눈에 보여주는 요약 대시보드입니다.',
    items: [
      { label: '위험도 분포 바', desc: '전체 쿼리 중 HIGH / MEDIUM / LOW 비율을 색상 바로 표시' },
      { label: '평균 Risk Score', desc: '모든 쿼리의 위험도 점수 평균 (0~100)' },
      { label: '최고 Risk Score', desc: '가장 위험한 단일 쿼리의 점수' },
      { label: '쿼리별 차트', desc: '각 쿼리(#01, #02...)의 Risk Score를 바 차트로 비교' },
    ],
  },
  {
    icon: '🔍',
    title: '쿼리 결과 카드',
    desc: '각 쿼리별 분석 결과를 펼쳐서 확인할 수 있습니다. HIGH 위험 쿼리는 자동으로 펼쳐집니다.',
    items: [
      { label: 'SQL 원문',        desc: '입력한 원본 SQL 확인' },
      { label: '문제 설명',       desc: 'AI가 분석한 이관 실패 원인' },
      { label: '감지된 패턴',     desc: '탐지된 이관 위험 패턴 목록 (P01~P22)' },
      { label: '권고 DDL',        desc: 'MySQL로 변환된 수정 쿼리 (복사 가능)' },
      { label: '예상 개선 효과',  desc: '성능 개선 예측치' },
    ],
  },
  {
    icon: '🚦',
    title: '위험도 기준',
    desc: 'Risk Score는 0~100점으로 이관 위험도를 수치화합니다.',
    levels: [
      { risk: 'HIGH',   score: '70점 이상', desc: '이관 시 즉시 오류 발생 가능. 반드시 수정 필요', color: 'text-red-400' },
      { risk: 'MEDIUM', score: '40~69점',   desc: '성능 저하 또는 결과 불일치 발생 가능',          color: 'text-yellow-400' },
      { risk: 'LOW',    score: '40점 미만', desc: '이관 가능하나 최적화 권장',                     color: 'text-emerald-400' },
    ],
  },
];

export { HELP_SECTIONS };
