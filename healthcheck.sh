#!/bin/bash
curl -s -o /dev/null -w "%{http_code}" 'https://apps.dos.ny.gov/PublicInquiryWeb/api/PublicInquiry/GetComplexSearchMatchingEntities' \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://apps.dos.ny.gov' \
  --data-raw '{"searchValue":"test","searchByTypeIndicator":"EntityName","searchExpressionIndicator":"Contains","entityStatusIndicator":"AllStatuses","entityTypeIndicator":["Corporation"],"listPaginationInfo":{"listStartRecord":1,"listEndRecord":1}}' \
  --max-time 10 | grep -q 200