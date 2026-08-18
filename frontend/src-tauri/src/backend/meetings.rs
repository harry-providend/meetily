//! Meeting and transcript operations against the backend.
//!
//! Wraps a [`BackendClient`] rather than extending it, so the transport stays unaware of which
//! aggregates exist and each aggregate gets its own module as the migration proceeds.

use crate::backend::client::{BackendClient, BackendError};
use crate::backend::dto::{
    MeetingCreateRequest, MeetingListResponse, MeetingResponse, MeetingUpdateRequest,
    TranscriptReplaceRequest, TranscriptResponse, TranscriptSearchResponse, TranscriptSegmentRequest,
};

/// Matches the server's `page_size` ceiling.
const MAX_PAGE_SIZE: i64 = 200;

pub struct MeetingsApi<'a> {
    client: &'a BackendClient,
}

impl<'a> MeetingsApi<'a> {
    pub fn new(client: &'a BackendClient) -> Self {
        Self { client }
    }

    /// Every meeting the signed-in user owns, oldest page first.
    ///
    /// Pages internally rather than exposing pagination: the sidebar has always shown the full
    /// list, and changing that is a UI decision, not something this layer should force.
    pub async fn list_all(&self) -> Result<Vec<MeetingResponse>, BackendError> {
        let mut collected: Vec<MeetingResponse> = Vec::new();
        let mut page = 1_i64;

        loop {
            let response: MeetingListResponse = self
                .client
                .get_with_query(
                    "/api/v1/meetings",
                    &[
                        ("page", page.to_string()),
                        ("page_size", MAX_PAGE_SIZE.to_string()),
                    ],
                )
                .await?;

            let received = response.items.len() as i64;
            collected.extend(response.items);

            if received < MAX_PAGE_SIZE || collected.len() as i64 >= response.total {
                return Ok(collected);
            }
            page += 1;
        }
    }

    pub async fn get(&self, meeting_id: &str) -> Result<MeetingResponse, BackendError> {
        self.client
            .get(&format!("/api/v1/meetings/{meeting_id}"))
            .await
    }

    /// Creates a meeting, optionally with its transcript in the same request.
    pub async fn create(
        &self,
        meeting_id: &str,
        title: &str,
        folder_path: Option<String>,
        segments: Vec<TranscriptSegmentRequest>,
    ) -> Result<MeetingResponse, BackendError> {
        let request = MeetingCreateRequest {
            id: meeting_id.to_string(),
            title: title.to_string(),
            folder_path,
            segments,
        };
        self.client.post("/api/v1/meetings", &request).await
    }

    pub async fn rename(
        &self,
        meeting_id: &str,
        title: &str,
    ) -> Result<MeetingResponse, BackendError> {
        let request = MeetingUpdateRequest {
            title: title.to_string(),
        };
        self.client
            .patch(&format!("/api/v1/meetings/{meeting_id}"), &request)
            .await
    }

    pub async fn delete(&self, meeting_id: &str) -> Result<(), BackendError> {
        self.client
            .delete(&format!("/api/v1/meetings/{meeting_id}"))
            .await
    }

    /// The whole transcript. `total` in the response is the full segment count.
    pub async fn transcript(&self, meeting_id: &str) -> Result<TranscriptResponse, BackendError> {
        self.client
            .get(&format!("/api/v1/meetings/{meeting_id}/transcript"))
            .await
    }

    pub async fn transcript_page(
        &self,
        meeting_id: &str,
        limit: i64,
        offset: i64,
    ) -> Result<TranscriptResponse, BackendError> {
        self.client
            .get_with_query(
                &format!("/api/v1/meetings/{meeting_id}/transcript"),
                &[("limit", limit.to_string()), ("offset", offset.to_string())],
            )
            .await
    }

    /// Replaces the transcript, archiving the previous segments as a version server-side.
    pub async fn replace_transcript(
        &self,
        meeting_id: &str,
        reason: &str,
        segments: Vec<TranscriptSegmentRequest>,
    ) -> Result<TranscriptResponse, BackendError> {
        let request = TranscriptReplaceRequest {
            reason: reason.to_string(),
            segments,
        };
        self.client
            .put(&format!("/api/v1/meetings/{meeting_id}/transcript"), &request)
            .await
    }

    pub async fn search_transcripts(
        &self,
        query: &str,
        limit: i64,
    ) -> Result<TranscriptSearchResponse, BackendError> {
        self.client
            .get_with_query(
                "/api/v1/transcripts/search",
                &[("query", query.to_string()), ("limit", limit.to_string())],
            )
            .await
    }
}
