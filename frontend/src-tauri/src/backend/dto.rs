//! Wire types mirroring the server's schemas. Field names match the JSON exactly, so a rename on
//! either side fails to compile rather than silently going missing.

use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct MeetingResponse {
    pub id: String,
    pub title: String,
    pub folder_path: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Deserialize)]
pub struct MeetingListResponse {
    pub items: Vec<MeetingResponse>,
    pub total: i64,
}

#[derive(Debug, Serialize)]
pub struct MeetingCreateRequest {
    pub id: String,
    pub title: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub folder_path: Option<String>,
    /// Sent with the meeting so finalisation is one request, and one server transaction.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub segments: Vec<TranscriptSegmentRequest>,
}

#[derive(Debug, Serialize)]
pub struct MeetingUpdateRequest {
    pub title: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TranscriptSegmentRequest {
    pub id: String,
    pub transcript: String,
    pub timestamp: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_start_time: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_end_time: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub duration: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speaker: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TranscriptSegmentResponse {
    pub id: String,
    pub transcript: String,
    pub timestamp: String,
    pub audio_start_time: Option<f64>,
    pub audio_end_time: Option<f64>,
    pub duration: Option<f64>,
    #[allow(dead_code)]
    pub speaker: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TranscriptResponse {
    #[allow(dead_code)]
    pub meeting_id: String,
    pub segments: Vec<TranscriptSegmentResponse>,
    /// Segment count for the whole meeting, not just the page returned.
    pub total: i64,
}

#[derive(Debug, Serialize)]
pub struct TranscriptReplaceRequest {
    pub reason: String,
    pub segments: Vec<TranscriptSegmentRequest>,
}

#[derive(Debug, Deserialize)]
pub struct TranscriptSearchHit {
    pub meeting_id: String,
    pub meeting_title: String,
    pub match_context: String,
    pub timestamp: String,
}

#[derive(Debug, Deserialize)]
pub struct TranscriptSearchResponse {
    pub hits: Vec<TranscriptSearchHit>,
}

#[derive(Debug, Deserialize)]
pub struct SummaryProcessResponse {
    pub status: String,
    pub result: Option<String>,
    pub english_cache: Option<serde_json::Value>,
    pub error: Option<String>,
    pub start_time: Option<String>,
    pub end_time: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SummaryCompleteRequest {
    pub result: String,
    /// Sent beside the document, never inside it, so version history stays free of cache state.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub english_cache: Option<serde_json::Value>,
    pub chunk_count: i64,
    pub processing_time: f64,
}

#[derive(Debug, Serialize)]
pub struct SummaryFailRequest {
    pub error: String,
}

#[derive(Debug, Serialize)]
pub struct SummaryUpsertRequest {
    pub status: String,
    pub result: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TranscriptVersionResponse {
    pub version: i64,
    pub reason: String,
    pub segment_count: i64,
    pub created_at: String,
}

#[derive(Debug, Deserialize)]
pub struct TranscriptVersionDetailResponse {
    pub segments_json: Vec<ArchivedSegment>,
}

/// One segment inside an archived transcript version.
#[derive(Debug, Deserialize)]
pub struct ArchivedSegment {
    pub transcript: String,
    pub timestamp: String,
    pub audio_start_time: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct SummaryVersionResponse {
    pub version: i64,
    pub reason: String,
    /// Decoded object, not the raw string the local schema stored.
    pub result_json: serde_json::Value,
    pub created_at: String,
}

#[derive(Debug, Deserialize)]
pub struct SummaryTemplateResponse {
    pub id: String,
    pub name: String,
    pub description: String,
    /// A JSON array of sections. Kept as a Value so this layer stays unaware of their shape.
    pub sections_json: serde_json::Value,
    pub is_builtin: bool,
    pub user_modified: bool,
    pub updated_at: String,
}

#[derive(Debug, Deserialize)]
pub struct SummaryTemplateListResponse {
    pub items: Vec<SummaryTemplateResponse>,
}

#[derive(Debug, Serialize)]
pub struct SummaryTemplateUpsertRequest {
    pub id: String,
    pub name: String,
    pub description: String,
    pub sections_json: serde_json::Value,
}

/// A template as shipped in the app bundle.
#[derive(Debug, Serialize)]
pub struct ShippedTemplate {
    pub id: String,
    pub name: String,
    pub description: String,
    pub sections_json: serde_json::Value,
}

#[derive(Debug, Serialize)]
pub struct TemplateSeedRequest {
    pub templates: Vec<ShippedTemplate>,
}

#[derive(Debug, Deserialize)]
pub struct TemplateSeedResponse {
    pub written: i64,
    pub skipped_user_modified: i64,
}

#[derive(Debug, Deserialize)]
pub struct TemplateImportResponse {
    pub imported: Vec<String>,
    #[allow(dead_code)]
    pub already_present: Vec<String>,
}
