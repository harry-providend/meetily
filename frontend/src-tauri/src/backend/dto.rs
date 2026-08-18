//! Wire types mirroring the server's Pydantic schemas. Field names match the JSON exactly, so a
//! rename on either side is a compile error here rather than a silently missing value.

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
    pub error: Option<String>,
    pub start_time: Option<String>,
    pub end_time: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct SummaryCompleteRequest {
    pub result: String,
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
