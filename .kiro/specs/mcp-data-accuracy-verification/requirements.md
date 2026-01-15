# Requirements Document

## Introduction

MCPサーバーのe-Statデータ取得機能の正確性を検証するシステムを構築する。複数のデータセットを対象に、API経由で取得したデータとe-Stat公式サイトから直接取得したデータを比較し、データ完全性・メタデータ正確性・API取得機能の信頼性を定量的に評価する。

## Glossary

- **MCP_Server**: estat-enhanced MCPサーバー
- **Raw_Data**: e-Stat公式サイトから直接ダウンロードした元データ
- **API_Data**: MCP APIを通じて取得したデータ
- **Verification_System**: データ正確性検証システム
- **Metadata_Analysis**: メタデータ分析結果
- **Completeness_Ratio**: データ完全性比率（取得データ数/期待データ数）

## Requirements

### Requirement 1: データセット検索・選定機能

**User Story:** As a data analyst, I want to search and select diverse datasets for verification, so that I can comprehensively test MCP data accuracy across different data types.

#### Acceptance Criteria

1. THE Verification_System SHALL search e-Stat using 10 different statistical keywords
2. WHEN searching with each keyword, THE Verification_System SHALL select one representative dataset
3. THE Verification_System SHALL ensure selected datasets vary in size (small: <10K, medium: 10K-100K, large: >100K records)
4. THE Verification_System SHALL record dataset metadata (ID, title, record count, categories) for each selection
5. THE Verification_System SHALL validate that selected datasets are accessible via both API and direct download

### Requirement 2: API経由データ取得機能

**User Story:** As a verification engineer, I want to retrieve datasets via MCP API with complete metadata analysis, so that I can capture all API-provided information for comparison.

#### Acceptance Criteria

1. WHEN retrieving data via API, THE MCP_Server SHALL provide complete metadata analysis
2. THE MCP_Server SHALL return OVERALL_TOTAL_NUMBER from e-Stat metadata
3. THE MCP_Server SHALL calculate theoretical record combinations from category dimensions
4. THE MCP_Server SHALL report actual retrieved record count
5. THE MCP_Server SHALL calculate and report completeness ratio
6. THE MCP_Server SHALL identify data structure details (categories, dimensions, time periods)
7. THE MCP_Server SHALL save retrieved data to S3 with timestamp and metadata

### Requirement 3: 直接ダウンロード機能

**User Story:** As a verification engineer, I want to download raw data directly from e-Stat, so that I can establish ground truth for comparison.

#### Acceptance Criteria

1. THE Verification_System SHALL download CSV/Excel files directly from e-Stat official site
2. THE Verification_System SHALL parse downloaded files into structured format
3. THE Verification_System SHALL extract metadata from official e-Stat dataset pages
4. THE Verification_System SHALL record official OVERALL_TOTAL_NUMBER from e-Stat metadata
5. THE Verification_System SHALL save raw data with original format preservation

### Requirement 4: データ比較・検証機能

**User Story:** As a quality assurance engineer, I want to compare API data with raw data systematically, so that I can identify discrepancies and measure accuracy.

#### Acceptance Criteria

1. THE Verification_System SHALL compare record counts between API_Data and Raw_Data
2. THE Verification_System SHALL validate data completeness ratios for accuracy
3. THE Verification_System SHALL compare metadata values (OVERALL_TOTAL_NUMBER, categories, dimensions)
4. THE Verification_System SHALL identify missing records in API_Data compared to Raw_Data
5. THE Verification_System SHALL detect duplicate records in API_Data
6. THE Verification_System SHALL calculate accuracy metrics (precision, recall, completeness)
7. THE Verification_System SHALL flag datasets with completeness ratio < 95%

### Requirement 5: メタデータ正確性検証機能

**User Story:** As a data governance specialist, I want to verify metadata accuracy between API and official sources, so that I can ensure metadata reliability.

#### Acceptance Criteria

1. THE Verification_System SHALL compare OVERALL_TOTAL_NUMBER between API and official e-Stat
2. THE Verification_System SHALL validate category counts and names
3. THE Verification_System SHALL verify dimension structures (area, time, categories)
4. THE Verification_System SHALL check data type classifications
5. THE Verification_System SHALL validate survey dates and update dates
6. THE Verification_System SHALL report metadata discrepancy rates

### Requirement 6: 検証レポート生成機能

**User Story:** As a project manager, I want comprehensive verification reports, so that I can assess MCP data quality and make informed decisions.

#### Acceptance Criteria

1. THE Verification_System SHALL generate summary reports for all 10 datasets
2. THE Verification_System SHALL calculate overall accuracy metrics across all datasets
3. THE Verification_System SHALL identify patterns in data discrepancies
4. THE Verification_System SHALL provide recommendations for MCP improvements
5. THE Verification_System SHALL export results in JSON and CSV formats
6. THE Verification_System SHALL include statistical significance tests for accuracy claims

### Requirement 7: 自動化・スケジューリング機能

**User Story:** As a system administrator, I want automated verification processes, so that I can regularly monitor MCP data quality without manual intervention.

#### Acceptance Criteria

1. THE Verification_System SHALL execute complete verification workflow automatically
2. THE Verification_System SHALL handle API rate limits and timeouts gracefully
3. THE Verification_System SHALL retry failed operations with exponential backoff
4. THE Verification_System SHALL log all operations with timestamps and status
5. THE Verification_System SHALL send notifications for critical accuracy issues
6. THE Verification_System SHALL maintain verification history for trend analysis

### Requirement 8: エラーハンドリング・復旧機能

**User Story:** As a reliability engineer, I want robust error handling, so that verification processes can recover from failures and provide meaningful diagnostics.

#### Acceptance Criteria

1. WHEN API calls fail, THE Verification_System SHALL log detailed error information
2. WHEN download failures occur, THE Verification_System SHALL attempt alternative download methods
3. THE Verification_System SHALL continue verification with remaining datasets when individual failures occur
4. THE Verification_System SHALL provide clear error categorization (network, API, parsing, validation)
5. THE Verification_System SHALL generate partial reports when complete verification is impossible