await test("loose", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
