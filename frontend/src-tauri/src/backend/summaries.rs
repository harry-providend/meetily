//! Summary generation against the backend.
//!
//! Generation is a run, not a single write: [`start`](SummariesApi::start) stashes the summary
//! being replaced, and exactly one of complete/fail/cancel ends the run. Failing to end it leaves
//! the row in PENDING, so every exit path from generation must call one of them.

use crate::backend::client::{BackendClient, BackendError};
use crate::backend::dto::{
    SummaryCompleteRequest, SummaryFailRequest, SummaryProcessResponse, SummaryUpsertRequest,
};

pub struct SummariesApi<'a> {
    client: &'a BackendClient,
}

impl<'a> SummariesApi<'a> {
    pub fn new(client: &'a BackendClient) -> Self {
        Self { client }
    }

    /// The current process row, or `None` when generation has never run for this meeting.
    pub async fn get(
        &self,
        meeting_id: &str,
    ) -> Result<Option<SummaryProcessResponse>, BackendError> {
        match self
            .client
            .get::<SummaryProcessResponse>(&format!("/api/v1/meetings/{meeting_id}/summary"))
            .await
        {
            Ok(process) => Ok(Some(process)),
            Err(BackendError::NotFound) => Ok(None),
            Err(e) => Err(e),
        }
    }

    pub async fn start(&self, meeting_id: &str) -> Result<SummaryProcessResponse, BackendError> {
        self.client
            .post(
                &format!("/api/v1/meetings/{meeting_id}/summary/generation"),
                &(),
            )
            .await
    }

    pub async fn complete(
        &self,
        meeting_id: &str,
        result: String,
        chunk_count: i64,
        processing_time: f64,
    ) -> Result<SummaryProcessResponse, BackendError> {
        let request = SummaryCompleteRequest {
            result,
            chunk_count,
            processing_time,
        };
        self.client
            .post(
                &format!("/api/v1/meetings/{meeting_id}/summary/generation/complete"),
                &request,
            )
            .await
    }

    pub async fn fail(
        &self,
        meeting_id: &str,
        error: &str,
    ) -> Result<SummaryProcessResponse, BackendError> {
        let request = SummaryFailRequest {
            error: error.to_string(),
        };
        self.client
            .post(
                &format!("/api/v1/meetings/{meeting_id}/summary/generation/fail"),
                &request,
            )
            .await
    }

    pub async fn cancel(&self, meeting_id: &str) -> Result<SummaryProcessResponse, BackendError> {
        self.client
            .post(
                &format!("/api/v1/meetings/{meeting_id}/summary/generation/cancel"),
                &(),
            )
            .await
    }

    /// Stores a summary the user wrote or edited directly, which is not a generation run.
    pub async fn save_directly(
        &self,
        meeting_id: &str,
        result: String,
    ) -> Result<SummaryProcessResponse, BackendError> {
        let request = SummaryUpsertRequest {
            status: "completed".to_string(),
            result: Some(result),
        };
        self.client
            .put(&format!("/api/v1/meetings/{meeting_id}/summary"), &request)
            .await
    }
}
