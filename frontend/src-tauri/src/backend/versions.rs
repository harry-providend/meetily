//! Transcript and summary version history.
//!
//! Restores go through the server as one request each: the local implementation wrapped
//! archive-then-replace in a transaction, and splitting that across HTTP calls would leave a
//! meeting with no transcript if the second call failed.

use crate::backend::client::{BackendClient, BackendError};
use crate::backend::dto::{
    SummaryVersionResponse, TranscriptVersionDetailResponse, TranscriptVersionResponse,
};

pub struct VersionsApi<'a> {
    client: &'a BackendClient,
}

impl<'a> VersionsApi<'a> {
    pub fn new(client: &'a BackendClient) -> Self {
        Self { client }
    }

    /// Newest version first, matching the order the picker displays.
    pub async fn list_transcript_versions(
        &self,
        meeting_id: &str,
    ) -> Result<Vec<TranscriptVersionResponse>, BackendError> {
        self.client
            .get(&format!(
                "/api/v1/meetings/{meeting_id}/transcript/versions"
            ))
            .await
    }

    pub async fn list_summary_versions(
        &self,
        meeting_id: &str,
    ) -> Result<Vec<SummaryVersionResponse>, BackendError> {
        self.client
            .get(&format!("/api/v1/meetings/{meeting_id}/summary/versions"))
            .await
    }

    pub async fn get_transcript_version(
        &self,
        meeting_id: &str,
        version: i64,
    ) -> Result<TranscriptVersionDetailResponse, BackendError> {
        self.client
            .get(&format!(
                "/api/v1/meetings/{meeting_id}/transcript/versions/{version}"
            ))
            .await
    }

    pub async fn get_summary_version(
        &self,
        meeting_id: &str,
        version: i64,
    ) -> Result<SummaryVersionResponse, BackendError> {
        self.client
            .get(&format!(
                "/api/v1/meetings/{meeting_id}/summary/versions/{version}"
            ))
            .await
    }

    /// Returns the restored segment count.
    pub async fn restore_transcript_version(
        &self,
        meeting_id: &str,
        version: i64,
    ) -> Result<usize, BackendError> {
        let restored: crate::backend::dto::TranscriptResponse = self
            .client
            .post(
                &format!("/api/v1/meetings/{meeting_id}/transcript/versions/{version}/restore"),
                &(),
            )
            .await?;
        Ok(restored.segments.len())
    }

    pub async fn restore_summary_version(
        &self,
        meeting_id: &str,
        version: i64,
    ) -> Result<(), BackendError> {
        let _: crate::backend::dto::SummaryProcessResponse = self
            .client
            .post(
                &format!("/api/v1/meetings/{meeting_id}/summary/versions/{version}/restore"),
                &(),
            )
            .await?;
        Ok(())
    }
}
