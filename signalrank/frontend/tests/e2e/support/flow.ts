import { expect, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { resolve } from "node:path";

export const syntheticResume = resolve(process.cwd(), "tests/fixtures/synthetic-resume.txt");

export const syntheticResumeFiles = {
  txt: {
    name: "synthetic-resume.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic resume fixture. No personal contact details."),
  },
  pdf: {
    name: "synthetic-resume.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4 synthetic fixture"),
  },
  docx: {
    name: "synthetic-resume.docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: Buffer.from("PK synthetic fixture"),
  },
};

export function uniqueEmail() {
  return `e2e-${randomUUID()}@example.test`;
}

export async function signUp(page: Page, email = uniqueEmail()) {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("fixture-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  return email;
}

export async function logIn(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("fixture-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

export async function completeOnboarding(page: Page, email?: string) {
  const account = email ?? await signUp(page);
  await page.getByLabel("resume").setInputFiles(syntheticResume);
  await page.getByRole("button", { name: "Build my profile" }).click();
  await expect(page.getByRole("heading", { name: "Confirm what you want next." })).toBeVisible();

  await finishOnboarding(page);
  return account;
}

export async function finishOnboarding(page: Page) {
  await page.getByPlaceholder("Type any role title").fill("Platform Engineer");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page
    .getByPlaceholder("Cities, regions, remote, or relocation")
    .fill("Remote");
  await page.getByRole("button", { name: "Top reputed" }).click();
  await page.getByRole("button", { name: "Save preferences and rank jobs" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Focus on the roles that fit." })).toBeVisible();
}

export async function openMatches(page: Page) {
  await page.getByRole("link", { name: "Matches" }).click();
  await expect(page).toHaveURL(/\/jobs$/);
  await expect(page.getByRole("heading", { name: "Your matches" })).toBeVisible();
}
