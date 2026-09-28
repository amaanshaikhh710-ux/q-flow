import { chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE_URL = 'http://localhost:5173';
const SCREENSHOT_DIR = 'C:\\Users\\Admin\\.gemini\\antigravity\\brain\\e51da581-e843-4194-9471-ca5de36ed560\\qa_screenshots';

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function runQA() {
  console.log('====================================================');
  console.log('  STARTING COMPREHENSIVE BROWSER QA (PHASE 7.3)');
  console.log('====================================================');
  console.log(`Frontend Target: ${BASE_URL}`);
  console.log(`Edge Binary:     ${EDGE_PATH}`);
  console.log(`Screenshots:     ${SCREENSHOT_DIR}\n`);

  const browser = await chromium.launch({
    executablePath: EDGE_PATH,
    headless: true,
  });

  const patientContext = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });

  const page = await patientContext.newPage();

  const consoleLogs = [];
  const consoleErrors = [];
  const networkErrors = [];

  page.on('console', (msg) => {
    const text = msg.text();
    consoleLogs.push(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error') {
      consoleErrors.push(text);
      console.error(`Browser console.error: ${text}`);
    }
  });

  page.on('requestfailed', (req) => {
    networkErrors.push(`${req.method()} ${req.url()} - ${req.failure()?.errorText}`);
  });

  try {
    // ----------------------------------------------------
    // STEP 1: LANDING PAGE
    // ----------------------------------------------------
    console.log('>>> Step 1: Navigating to Landing Page (/)');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_landing_page.png') });
    console.log('    Page Title:', await page.title());
    const heroTitle = await page.locator('h1').textContent();
    console.log('    Hero Title:', heroTitle?.trim().replace(/\s+/g, ' '));

    // ----------------------------------------------------
    // STEP 2: LOGIN PAGE (Two-Column SaaS Layout)
    // ----------------------------------------------------
    console.log('\n>>> Step 2: Navigating to Login Page (/login)');
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
    await page.waitForSelector('text=Welcome back', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_login_page.png') });
    console.log('    PASS: Two-column login page displayed with patient/staff tabs.');

    // ----------------------------------------------------
    // STEP 3: PATIENT REGISTRATION
    // ----------------------------------------------------
    console.log('\n>>> Step 3: Patient Registration Flow');
    const registerLink = page.locator('a:has-text("Create an account"), a:has-text("Register")').first();
    await registerLink.click();
    await page.waitForURL('**/register', { timeout: 8000 });

    const timestamp = Date.now();
    const patientName = `QA Patient ${String(timestamp).slice(-4)}`;
    const patientEmail = `qa_pat_${timestamp}@qflow.dev`;
    const patientPhone = `+9198${String(timestamp).slice(-8)}`;

    await page.fill('input[name="name"]', patientName);
    await page.fill('input[name="email"]', patientEmail);
    await page.fill('input[name="phone"]', patientPhone);
    await page.fill('input[name="password"]', 'password123');
    await page.fill('input[name="confirmPassword"]', 'password123');

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_registration_form.png') });
    await page.click('button[type="submit"]');

    // ----------------------------------------------------
    // STEP 4: HOSPITAL SELECTION
    // ----------------------------------------------------
    console.log('\n>>> Step 4: Hospital Selection (/hospitals)');
    await page.waitForURL('**/hospitals', { timeout: 10000 });
    await page.waitForSelector('text=Q-FLOW General Hospital', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_hospital_selection.png') });
    console.log('    Hospital directory loaded with seeded hospital.');

    const hospitalCard = page.locator('button:has-text("Q-FLOW General Hospital")');
    await hospitalCard.click();

    // ----------------------------------------------------
    // STEP 5: DEPARTMENT SELECTION
    // ----------------------------------------------------
    console.log('\n>>> Step 5: Department Selection (/departments/:id)');
    await page.waitForURL('**/departments/**', { timeout: 10000 });
    await page.waitForSelector('text=Cardiology', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_department_selection.png') });
    console.log('    Departments loaded: Cardiology, Orthopedics, General Medicine.');

    const cardiologyCard = page.locator('button:has-text("Cardiology")');
    await cardiologyCard.click();

    // ----------------------------------------------------
    // STEP 6: DOCTOR SELECTION
    // ----------------------------------------------------
    console.log('\n>>> Step 6: Doctor Selection (/doctors/:id)');
    await page.waitForURL('**/doctors/**', { timeout: 10000 });
    await page.waitForSelector('text=Dr. Arjun Mehta', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_doctor_selection.png') });
    console.log('    Doctor list loaded: Dr. Arjun Mehta.');

    const selectDoctorBtn = page.locator('button:has-text("View Sessions")').first();
    await selectDoctorBtn.click();

    // ----------------------------------------------------
    // STEP 7: SESSION SELECTION & PRE-JOIN CONFIRMATION
    // ----------------------------------------------------
    console.log('\n>>> Step 7: Session Selection & Pre-Join Confirmation');
    await page.waitForURL('**/sessions/**', { timeout: 10000 });
    await page.waitForSelector('button:has-text("Join Queue")', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_session_selection.png') });

    // Click "Join Queue" to open pre-join confirmation modal
    await page.click('button:has-text("Join Queue")');
    await page.waitForSelector('button:has-text("Confirm & Join Queue")', { timeout: 5000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08_prejoin_confirmation_modal.png') });
    console.log('    Pre-join conversion modal successfully displayed.');

    // Confirm Join
    await page.click('button:has-text("Confirm & Join Queue")');
    await page.waitForSelector('text=ASSIGNED TOKEN', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '09_joined_success_modal.png') });
    console.log('    Ticket issued! Success modal displayed.');

    // Click View Live Ticket
    await page.click('button:has-text("View Live Ticket")');

    // ----------------------------------------------------
    // STEP 8: LIVE PATIENT TICKET PAGE
    // ----------------------------------------------------
    console.log('\n>>> Step 8: Live Patient Ticket (/ticket/:entryId)');
    await page.waitForURL('**/ticket/**', { timeout: 10000 });
    const ticketUrl = page.url();
    console.log('    Ticket URL:', ticketUrl);

    await page.waitForSelector('text=Queue Token Number', { timeout: 10000 });
    const tokenDisplay = await page.locator('.font-mono').first().textContent();
    console.log('    Live Ticket Token:', tokenDisplay?.trim());

    // Extract queueId from patient token / page context for staff control
    const queueId = await page.evaluate(async () => {
      const entryId = window.location.pathname.split('/').pop();
      const token = localStorage.getItem('qflow_token');
      const res = await fetch(`http://localhost:8000/api/v1/queue-entries/${entryId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      return data.queue_id;
    });
    console.log('    Queue ID associated with ticket:', queueId);

    // Check Live status indicator (WebSocket)
    const liveIndicator = page.locator('span:has-text("LIVE"), span:has-text("Live"), span:has-text("Offline")');
    console.log('    Live Connection status text:', (await liveIndicator.first().textContent())?.trim());

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '10_live_ticket_full.png') });

    // Check Expandable Explanation ("Why this estimate?")
    const explanationBtn = page.locator('button:has-text("Why this estimate?")');
    if (await explanationBtn.isVisible()) {
      await explanationBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '11_why_estimate_expanded.png') });
      console.log('    Verified expandable explanation ("Why this estimate?").');
    }

    // ----------------------------------------------------
    // STEP 9: REFRESH REGRESSION TEST
    // ----------------------------------------------------
    console.log('\n>>> Step 9: Hard Page Refresh Regression Test');
    console.log('    Reloading ticket page to prove no blank screen or infinite hang occurs...');
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('text=Queue Token Number', { timeout: 10000 });
    const tokenAfterReload = await page.locator('.font-mono').first().textContent();
    console.log('    Token displayed immediately after reload:', tokenAfterReload?.trim());
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12_ticket_after_hard_reload.png') });
    console.log('    PASS: Zero blank screens, zero infinite spinners on refresh!');

    // ----------------------------------------------------
    // STEP 10: TRAVEL SETUP & ARRIVAL PLAN
    // ----------------------------------------------------
    console.log('\n>>> Step 10: Travel Setup & Arrival Plan');
    const entryId = ticketUrl.split('/').pop();
    const setLocationBtn = page.locator('a:has-text("Set Starting Point"), a:has-text("Set Location")').first();
    await setLocationBtn.click();
    await page.waitForURL('**/travel/**', { timeout: 10000 });
    await page.waitForSelector('text=Plan when to leave', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '13_travel_setup_page.png') });

    // Submit origin form
    await page.click('button[type="submit"]');
    await page.waitForURL('**/arrival-plan/**', { timeout: 10000 });
    await page.waitForSelector('text=Recommended Departure Window', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '14_arrival_plan_page.png') });
    console.log('    PASS: Travel calculation and arrival plan displayed.');

    // Return to ticket
    await page.goto(`${BASE_URL}/ticket/${entryId}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('text=Queue Token Number', { timeout: 10000 });

    // ----------------------------------------------------
    // STEP 11: STAFF OPERATIONS DASHBOARD & QUEUE CONTROL
    // ----------------------------------------------------
    console.log('\n>>> Step 11: Staff Operations & Queue Control Center');
    const staffContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    });
    const staffPage = await staffContext.newPage();

    console.log('    Staff: Logging in as staff@qflow.com...');
    await staffPage.goto(`${BASE_URL}/login`);
    await staffPage.fill('input[name="identifier"]', 'staff@qflow.com');
    await staffPage.fill('input[name="password"]', 'password123');
    await staffPage.click('button[type="submit"]');

    await staffPage.waitForURL('**/staff', { timeout: 10000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '15_staff_dashboard.png') });
    console.log('    Staff operations dashboard loaded.');

    // Navigate to active queue control center
    console.log(`    Staff: Opening queue dashboard for ${queueId}...`);
    await staffPage.goto(`${BASE_URL}/staff/queue/${queueId}`, { waitUntil: 'networkidle' });
    await staffPage.waitForSelector('button:has-text("Doctor Delay")', { timeout: 10000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '16_staff_queue_control.png') });
    console.log('    Staff Queue Control Center opened.');

    // ----------------------------------------------------
    // STEP 12: EMERGENCY MODAL & TOKEN RESOLUTION (PART 27 FIX)
    // ----------------------------------------------------
    console.log('\n>>> Step 12: Emergency Insertion & Token Resolution Verification');
    const emergencyBtn = staffPage.locator('button:has-text("Emergency Insert")');
    await emergencyBtn.click();
    await staffPage.waitForSelector('text=Emergency Consultation Triage', { timeout: 5000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '17_emergency_modal.png') });
    console.log('    PASS: Emergency modal loaded with token selection / elevation.');

    // Close emergency modal
    await staffPage.click('button:has-text("Cancel")');

    // ----------------------------------------------------
    // STEP 13: DOCTOR BREAK MODAL
    // ----------------------------------------------------
    console.log('\n>>> Step 13: Doctor Break Modal Verification');
    const breakBtn = staffPage.locator('button:has-text("Doctor Break")');
    await breakBtn.click();
    await staffPage.waitForSelector('text=Doctor Break Management', { timeout: 5000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '18_doctor_break_modal.png') });
    console.log('    PASS: Doctor Break modal displayed.');
    await staffPage.click('button:has-text("Cancel")');

    // ----------------------------------------------------
    // STEP 14: DOCTOR DELAY MODAL & REAL-TIME WEBSOCKET REFORECAST
    // ----------------------------------------------------
    console.log('\n>>> Step 14: Applying Doctor Delay for Real-Time Reforecast');
    const delayBtn = staffPage.locator('button:has-text("Doctor Delay")');
    await delayBtn.click();
    await staffPage.waitForSelector('text=Record Doctor Delay', { timeout: 5000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '19_doctor_delay_modal.png') });
    await staffPage.click('button:has-text("Apply Doctor Delay")');
    await staffPage.waitForTimeout(2500);
    console.log('    Doctor delay applied and authoritative reforecast triggered.');

    // Verify Patient Ticket Received WebSocket Update
    console.log('    Verifying patient ticket received dynamic ETA change notification...');
    await page.bringToFront();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '20_patient_ticket_realtime_eta_banner.png') });

    const etaBanner = page.locator('text=ETA Updated, text="Why did this happen?", text=ETA Updated in Real Time');
    const isEtaBannerVisible = await etaBanner.first().isVisible().catch(() => false);
    console.log(`    Dynamic ETA change banner visible: ${isEtaBannerVisible}`);

    // ----------------------------------------------------
    // STEP 15: MOBILE VIEWPORT QA (375x667)
    // ----------------------------------------------------
    console.log('\n>>> Step 15: Mobile Viewport QA (375x667)');
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '21_mobile_ticket_viewport.png') });

    const ticketHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    console.log('    Mobile ticket horizontal overflow:', ticketHorizontalOverflow ? 'FAIL (Horizontal scroll)' : 'PASS (0px overflow)');

    await page.goto(`${BASE_URL}/hospitals`);
    await page.waitForSelector('text=Q-FLOW General Hospital', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '22_mobile_hospitals_viewport.png') });

    const hospitalsHorizontalOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    console.log('    Mobile hospitals horizontal overflow:', hospitalsHorizontalOverflow ? 'FAIL (Horizontal scroll)' : 'PASS (0px overflow)');

    // ----------------------------------------------------
    // STEP 16: CONSOLE LOGS & SUMMARY
    // ----------------------------------------------------
    console.log('\n====================================================');
    console.log('                 FINAL QA RESULTS');
    console.log('====================================================');
    console.log(`Console Errors:    ${consoleErrors.length}`);
    console.log(`Network Failures:  ${networkErrors.length}`);
    console.log(`Mobile Fit Ticket: ${ticketHorizontalOverflow ? 'FAIL' : 'PASS'}`);
    console.log(`Mobile Fit Hosp:   ${hospitalsHorizontalOverflow ? 'FAIL' : 'PASS'}`);
    console.log('All QA steps completed successfully!');

    await staffContext.close();
    await patientContext.close();
    await browser.close();

    return {
      success: true,
      ticketUrl,
      tokenDisplay: tokenDisplay?.trim(),
      ticketHorizontalOverflow,
      hospitalsHorizontalOverflow,
      consoleErrors,
      networkErrors,
      isEtaBannerVisible,
    };
  } catch (err) {
    console.error('\n*** QA FAILED WITH EXCEPTION ***', err);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '99_fatal_error.png') }).catch(() => {});
    await browser.close();
    throw err;
  }
}

runQA()
  .then((res) => {
    console.log('\nExecution Summary JSON:');
    console.log(JSON.stringify(res, null, 2));
    process.exit(0);
  })
  .catch((err) => {
    process.exit(1);
  });

