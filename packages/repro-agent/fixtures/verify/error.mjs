test.fixme("symptom", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Welcome" })).toBeVisible();
});
