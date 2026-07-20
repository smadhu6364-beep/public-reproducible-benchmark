# Corpus audit report

Report-only. No manifest, ground-truth, or processed-text file was modified by this run.

**Summary: 19 PASS / 1 WARN / 1 FAIL** (of 21 included projects)

## P-MAR-SecondIdentityTargetingSocialProtection - FAIL
- Check 1 (page-range): PASS - declared=[8, 9, 36] found=[8, 36] total_pages=48
  - raw scan detail: {'key_risks_pages': [36], 'sort_table_pages': [8]}
- Check 2 (leak check): FAIL
  - [verbatim_phrase] risk=R01: `the first Identity and Targeting for Social Protection`
  - [distinctive_code] risk=R01: `P155198`

## P-UK-PadeswoodCCUS - WARN
- Check 1 (page-range): WARN - declared=[10, 11, 14, 15] found=[9, 10, 14] total_pages=17
  - pages with a heading/SORT match OUTSIDE the declared excision range: [9]
  - raw scan detail: {'3.4 Risk Appraisal': [9, 10], '5.4 Financial Risks': [14]}
- Check 2 (leak check): PASS

## P-AFW-HealthSecurityPhase3 - PASS
- Check 1 (page-range): PASS - declared=[11, 46, 47] found=[11, 46] total_pages=84
  - raw scan detail: {'key_risks_pages': [46], 'sort_table_pages': [11]}
- Check 2 (leak check): PASS

## P-ALB-CitizenServiceDelivery - PASS
- Check 1 (page-range): PASS - declared=[4, 27] found=[4, 27] total_pages=91
  - raw scan detail: {'key_risks_pages': [27], 'sort_table_pages': [4]}
- Check 2 (leak check): PASS

## P-BFA-EconomicOpportunitiesResilience - PASS
- Check 1 (page-range): PASS - declared=[8, 9, 35, 36] found=[9, 35] total_pages=51
  - raw scan detail: {'key_risks_pages': [35], 'sort_table_pages': [9]}
- Check 2 (leak check): PASS

## P-BGD-SocialProtectionResilience - PASS
- Check 1 (page-range): PASS - declared=[9, 34, 35, 36] found=[9, 35] total_pages=51
  - raw scan detail: {'key_risks_pages': [35], 'sort_table_pages': [9]}
- Check 2 (leak check): PASS

## P-GTM-SmartPublicFinances - PASS
- Check 1 (page-range): PASS - declared=[8, 9, 25, 37, 38] found=[8, 25, 37] total_pages=43
  - raw scan detail: {'key_risks_pages': [25, 37], 'sort_table_pages': [8]}
- Check 2 (leak check): PASS

## P-IND-ChhattisgarhAcceleratedLearning - PASS
- Check 1 (page-range): PASS - declared=[8, 32] found=[8, 32] total_pages=65
  - raw scan detail: {'key_risks_pages': [32], 'sort_table_pages': [8]}
- Check 2 (leak check): PASS

## P-JOR-InnovativeStartupsSMEsFund2 - PASS
- Check 1 (page-range): PASS - declared=[7, 8, 35] found=[7, 35] total_pages=40
  - raw scan detail: {'key_risks_pages': [35], 'sort_table_pages': [7]}
- Check 2 (leak check): PASS

## P-KHM-BasicEducationImprovement - PASS
- Check 1 (page-range): PASS - declared=[9, 30, 31] found=[9, 31] total_pages=40
  - raw scan detail: {'key_risks_pages': [31], 'sort_table_pages': [9]}
- Check 2 (leak check): PASS

## P-MEX-SustainableValueChains - PASS
- Check 1 (page-range): PASS - declared=[7, 8, 33, 34] found=[7, 8, 33] total_pages=43
  - raw scan detail: {'key_risks_pages': [33], 'sort_table_pages': [7, 8]}
- Check 2 (leak check): PASS

## P-MNG-ThirdEnergySector - PASS
- Check 1 (page-range): PASS - declared=[9, 28, 29] found=[9, 28] total_pages=50
  - raw scan detail: {'key_risks_pages': [28], 'sort_table_pages': [9]}
- Check 2 (leak check): PASS

## P-NGA-AgroProcessingLivelihood - PASS
- Check 1 (page-range): PASS - declared=[6, 7, 27, 28, 29] found=[6, 27, 28] total_pages=102
  - raw scan detail: {'key_risks_pages': [27], 'sort_table_pages': [6, 27, 28]}
- Check 2 (leak check): PASS

## P-PAK-ResilientAccessibleMicrofinance - PASS
- Check 1 (page-range): PASS - declared=[8, 9, 29, 30] found=[9, 29] total_pages=35
  - raw scan detail: {'key_risks_pages': [29], 'sort_table_pages': [9]}
- Check 2 (leak check): PASS

## P-PER-ArequipaColca - PASS
- Check 1 (page-range): PASS - declared=[7, 8, 32, 33, 34, 35] found=[7, 8, 34] total_pages=42
  - raw scan detail: {'key_risks_pages': [34], 'sort_table_pages': [7, 8]}
- Check 2 (leak check): PASS

## P-SLE-ConnectivityAgMarketInfra - PASS
- Check 1 (page-range): PASS - declared=[10, 11, 37, 38, 39] found=[10, 11, 38] total_pages=75
  - raw scan detail: {'key_risks_pages': [38], 'sort_table_pages': [10, 11, 38]}
- Check 2 (leak check): PASS

## P-SRB-CompetitivenessJobs - PASS
- Check 1 (page-range): PASS - declared=[9, 10, 30, 31, 32] found=[9, 10, 30, 31] total_pages=108
  - raw scan detail: {'key_risks_pages': [30], 'sort_table_pages': [9, 10, 30, 31]}
- Check 2 (leak check): PASS

## P-STP-YouthEmployment - PASS
- Check 1 (page-range): PASS - declared=[17, 18, 44, 45] found=[18, 44] total_pages=53
  - raw scan detail: {'key_risks_pages': [44], 'sort_table_pages': [18]}
- Check 2 (leak check): PASS

## P-UGA-IntegratedWaterMgmtDev - PASS
- Check 1 (page-range): PASS - declared=[9, 10, 27, 28, 78, 79] found=[10, 27, 78] total_pages=127
  - raw scan detail: {'key_risks_pages': [27, 78], 'sort_table_pages': [10, 27]}
- Check 2 (leak check): PASS

## P-UK-FreeBreakfastClubs - PASS
- Check 1 (page-range): SKIPPED - HTML-only publication, no PDF/pagination - see check2b
- Check 2 (leak check): PASS
- Check 2b (live HTML re-fetch, FreeBreakfastClubs only): PASS

## P-UK-HyNetCCUSCluster - PASS
- Check 1 (page-range): PASS - declared=[13, 14, 20, 21, 27, 32, 36, 37, 38] found=[13, 20, 27, 32, 36] total_pages=45
  - raw scan detail: {'1.6 Deliverability and risks': [13], '2.5 Identify high level potential risks': [20], '3.7 Risk Appraisal': [27], '4.2.4 Cluster-level commercial risk assessment': [32], '5.7 Financial risks': [36]}
- Check 2 (leak check): PASS
