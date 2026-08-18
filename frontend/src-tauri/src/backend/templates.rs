//! Summary templates. Shipped content stays in the app bundle and the server holds only row state,
//! so seeding is a push from here.

use crate::backend::client::{BackendClient, BackendError};
use crate::backend::dto::{
    ShippedTemplate, SummaryTemplateResponse, SummaryTemplateUpsertRequest, TemplateImportResponse,
    TemplateSeedRequest, TemplateSeedResponse,
};

pub struct TemplatesApi<'a> {
    client: &'a BackendClient,
}

impl<'a> TemplatesApi<'a> {
    pub fn new(client: &'a BackendClient) -> Self {
        Self { client }
    }

    /// Builtins first, then by name, as the picker displays them.
    pub async fn list(&self) -> Result<Vec<SummaryTemplateResponse>, BackendError> {
        let response: crate::backend::dto::SummaryTemplateListResponse =
            self.client.get("/api/v1/templates").await?;
        Ok(response.items)
    }

    pub async fn get(
        &self,
        template_id: &str,
    ) -> Result<Option<SummaryTemplateResponse>, BackendError> {
        match self
            .client
            .get::<SummaryTemplateResponse>(&format!("/api/v1/templates/{template_id}"))
            .await
        {
            Ok(template) => Ok(Some(template)),
            Err(BackendError::NotFound) => Ok(None),
            Err(e) => Err(e),
        }
    }

    /// Records a user edit. Editing a shipped template leaves it shipped, so it can still be reset.
    pub async fn save(
        &self,
        id: &str,
        name: &str,
        description: &str,
        sections_json: serde_json::Value,
    ) -> Result<SummaryTemplateResponse, BackendError> {
        let request = SummaryTemplateUpsertRequest {
            id: id.to_string(),
            name: name.to_string(),
            description: description.to_string(),
            sections_json,
        };
        self.client.put("/api/v1/templates", &request).await
    }

    pub async fn delete(&self, template_id: &str) -> Result<(), BackendError> {
        self.client
            .delete(&format!("/api/v1/templates/{template_id}"))
            .await
    }

    /// Applies the bundle's templates. The server skips any row the user has edited.
    pub async fn seed(
        &self,
        templates: Vec<ShippedTemplate>,
    ) -> Result<TemplateSeedResponse, BackendError> {
        self.client
            .post("/api/v1/templates/seed", &TemplateSeedRequest { templates })
            .await
    }

    /// One-time import of pre-SQLite templates found on disk. Never overwrites.
    pub async fn import(
        &self,
        templates: Vec<ShippedTemplate>,
    ) -> Result<TemplateImportResponse, BackendError> {
        self.client
            .post("/api/v1/templates/import", &TemplateSeedRequest { templates })
            .await
    }

    /// Clears the edited flag, so the next seed restores the shipped content.
    pub async fn reset(
        &self,
        template_id: &str,
    ) -> Result<SummaryTemplateResponse, BackendError> {
        self.client
            .post(&format!("/api/v1/templates/{template_id}/reset"), &())
            .await
    }
}
