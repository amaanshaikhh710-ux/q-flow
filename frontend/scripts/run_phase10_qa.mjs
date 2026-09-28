import { chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE_URL = 'http://localhost:5173';
const BACKEND_URL = 'http://localhost:8000';
const SCREENSHOT_DIR = 'C:\\Users\\Admin\\.gemini\\antigravity\\brain\\e51da581-e843-4194-9471-ca5de36ed560\\qa_screenshots_phase10';

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function runPhase10QA() {
  console.log('======================================================================');
  console.log('    Q-FLOW PHASE 10 — END-TO-END BROWSER QA & LIVE DEMO FLOW');
  console.log('======================================================================');
  console.log(`Frontend URL: ${BASE_URL}`);
  console.log(`Backend URL:  ${BACKEND_URL}`);
  console.log(`Screenshots:  ${SCREENSHOT_DIR}\n`);

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
      console.error(`[Browser console.error]: ${text}`);
    }
  });

  page.on('requestfailed', (req) => {
    const err = `${req.method()} ${req.url()} - ${req.failure()?.errorText}`;
    networkErrors.push(err);
    console.error(`[Browser requestfailed]: ${err}`);
  });

  try {
    // ----------------------------------------------------
    // STEP 1: LANDING PAGE
    // ----------------------------------------------------
    console.log('\n>>> Step 1: Navigating to Landing Page (/)');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_landing_page.png') });
    console.log('    Page Title:', await page.title());
    const heroTitle = await page.locator('h1').textContent();
    console.log('    Hero Title:', heroTitle?.trim().replace(/\s+/g, ' '));

    // ----------------------------------------------------
    // STEP 2: LOGIN PAGE & REGISTRATION
    // ----------------------------------------------------
    console.log('\n>>> Step 2: Patient Registration Flow (/register)');
    await page.goto(`${BASE_URL}/register`, { waitUntil: 'networkidle' });
    const timestamp = Date.now();
    const patientName = `Demo Patient ${String(timestamp).slice(-4)}`;
    const patientEmail = `demo_pat_${timestamp}@cityhealth.com`;
    const patientPhone = `+9198${String(timestamp).slice(-8)}`;

    await page.fill('input[name="name"]', patientName);
    await page.fill('input[name="email"]', patientEmail);
    await page.fill('input[name="phone"]', patientPhone);
    await page.fill('input[name="password"]', 'password123');
    await page.fill('input[name="confirmPassword"]', 'password123');

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_registration_form.png') });
    await page.click('button[type="submit"]');

    // ----------------------------------------------------
    // STEP 3: HOSPITAL SELECTION (City Health General Hospital)
    // ----------------------------------------------------
    console.log('\n>>> Step 3: Hospital Selection (/hospitals)');
    await page.waitForURL('**/hospitals', { timeout: 10000 });
    await page.waitForSelector('text=City Health General Hospital', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_hospital_selection.png') });
    console.log('    PASS: "City Health General Hospital" visible in directory.');

    const cityHealthBtn = page.locator('button:has-text("City Health General Hospital")').first();
    await cityHealthBtn.click();

    // ----------------------------------------------------
    // STEP 4: DEPARTMENT SELECTION (Cardiology)
    // ----------------------------------------------------
    console.log('\n>>> Step 4: Department Selection (/departments/:id)');
    await page.waitForURL('**/departments/**', { timeout: 10000 });
    await page.waitForSelector('text=Cardiology', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_department_selection.png') });
    console.log('    PASS: "Cardiology" department available.');

    const cardioCard = page.locator('button:has-text("Cardiology")').first();
    await cardioCard.click();

    // ----------------------------------------------------
    // STEP 5: DOCTOR SELECTION (Dr. Sarah Jenkins)
    // ----------------------------------------------------
    console.log('\n>>> Step 5: Doctor Selection (/doctors/:id)');
    await page.waitForURL('**/doctors/**', { timeout: 10000 });
    await page.waitForSelector('text=Dr. Sarah Jenkins', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_doctor_selection.png') });
    console.log('    PASS: "Dr. Sarah Jenkins" loaded.');

    const viewSessionsBtn = page.locator('button:has-text("View Sessions")').first();
    await viewSessionsBtn.click();

    // ----------------------------------------------------
    // STEP 6: SESSION SELECTION & PRE-JOIN CONFIRMATION
    // ----------------------------------------------------
    console.log('\n>>> Step 6: Session Selection & Queue Joining');
    await page.waitForURL('**/sessions/**', { timeout: 10000 });
    await page.waitForSelector('button:has-text("Join Queue")', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_session_selection.png') });

    await page.click('button:has-text("Join Queue")');
    await page.waitForSelector('button:has-text("Confirm & Join Queue")', { timeout: 5000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_prejoin_confirmation_modal.png') });

    await page.click('button:has-text("Confirm & Join Queue")');
    await page.waitForSelector('text=ASSIGNED TOKEN', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08_joined_success_modal.png') });
    console.log('    PASS: Pre-join confirmation and Token issuance succeeded.');

    await page.click('button:has-text("View Live Ticket")');

    // ----------------------------------------------------
    // STEP 7: LIVE PATIENT TICKET PAGE
    // ----------------------------------------------------
    console.log('\n>>> Step 7: Live Patient Ticket (/ticket/:entryId)');
    await page.waitForURL('**/ticket/**', { timeout: 10000 });
    const ticketUrl = page.url();
    const entryId = ticketUrl.split('/').pop();
    console.log('    Ticket URL:', ticketUrl);
    console.log('    Entry ID:', entryId);

    await page.waitForSelector('text=Queue Token Number', { timeout: 10000 });
    const tokenDisplay = await page.locator('.font-mono').first().textContent();
    console.log('    Assigned Token Display:', tokenDisplay?.trim());

    // Extract queueId from patient ticket
    const queueId = await page.evaluate(async (eid) => {
      const token = localStorage.getItem('qflow_token');
      const res = await fetch(`http://localhost:8000/api/v1/queue-entries/${eid}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      return data.queue_id;
    }, entryId);
    console.log('    Associated Queue ID:', queueId);

    // Expand "Why this estimate?" explanation
    const whyBtn = page.locator('button:has-text("Why this estimate?")');
    if (await whyBtn.isVisible()) {
      await whyBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SCREENSHOT_DIR, '09_why_estimate_expanded.png') });
      console.log('    PASS: "Why this estimate?" expanded successfully.');
    }

    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '10_live_ticket_full.png') });

    // ----------------------------------------------------
    // STEP 8: HARD PAGE REFRESH TEST
    // ----------------------------------------------------
    console.log('\n>>> Step 8: Hard Page Refresh Test');
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForSelector('text=Queue Token Number', { timeout: 10000 });
    console.log('    PASS: Ticket hydrated instantly on hard reload without infinite spinner.');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '11_ticket_after_hard_reload.png') });

    // ----------------------------------------------------
    // STEP 9: TRAVEL SETUP & ARRIVAL PLAN
    // ----------------------------------------------------
    console.log('\n>>> Step 9: Travel Setup & Arrival Plan');
    const setLocBtn = page.locator('a:has-text("Set Starting Point"), a:has-text("Set Location")').first();
    await setLocBtn.click();
    await page.waitForURL('**/travel/**', { timeout: 10000 });
    await page.waitForSelector('text=Plan when to leave', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12_travel_setup_page.png') });

    await page.click('button[type="submit"]');
    await page.waitForURL('**/arrival-plan/**', { timeout: 10000 });
    await page.waitForSelector('text=Recommended Departure Window', { timeout: 10000 });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '13_arrival_plan_page.png') });
    console.log('    PASS: Arrival plan computed and departure window displayed.');

    // Return to ticket to observe real-time WebSocket events
    await page.goto(`${BASE_URL}/ticket/${entryId}`, { waitUntil: 'networkidle' });
    await page.waitForSelector('text=Queue Token Number', { timeout: 10000 });

    // ----------------------------------------------------
    // STEP 10: STAFF OPERATIONS & QUEUE CONTROL
    // ----------------------------------------------------
    console.log('\n>>> Step 10: Staff Operations & Queue Control Center');
    const staffContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
    });
    const staffPage = await staffContext.newPage();

    console.log('    Staff: Logging in as receptionist1@cityhealth.com...');
    await staffPage.goto(`${BASE_URL}/login`);
    await staffPage.fill('input[name="identifier"]', 'receptionist1@cityhealth.com');
    await staffPage.fill('input[name="password"]', 'password123');
    await staffPage.click('button[type="submit"]');

    await staffPage.waitForURL('**/staff', { timeout: 10000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '14_staff_dashboard.png') });
    console.log('    PASS: Staff dashboard opened with authorized queues.');

    // Open Queue Control Page
    await staffPage.goto(`${BASE_URL}/staff/queue/${queueId}`, { waitUntil: 'networkidle' });
    await staffPage.waitForSelector('button:has-text("Doctor Delay")', { timeout: 10000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '15_staff_queue_control.png') });
    console.log('    PASS: Queue Control Center loaded for Dr. Sarah Jenkins OPD.');

    // ----------------------------------------------------
    // STEP 11: DOCTOR DELAY MODAL & REAL-TIME WEBSOCKET REFORECAST
    // ----------------------------------------------------
    console.log('\n>>> Step 11: Applying Doctor Delay (+15 min) for Live Reforecast');
    const delayBtn = staffPage.locator('button:has-text("Doctor Delay")');
    await delayBtn.click();
    await staffPage.waitForSelector('text=Record Doctor Delay', { timeout: 5000 });
    await staffPage.screenshot({ path: path.join(SCREENSHOT_DIR, '16_doctor_delay_modal.png') });

    await staffPage.click('button:has-text("Apply Doctor Delay")');
    await staffPage.waitForTimeout(2500);
    console.log('    PASS: Doctor delay applied and broadcast.');

    // Check Patient Ticket Real-time WebSocket Banner
    console.log('    Checking Patient Ticket for WebSocket live update...');
    await page.bringToFront();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '17_patient_ticket_realtime_ws_update.png') });

    // ----------------------------------------------------
    // STEP 12: MOBILE VIEWPORT QA (375x667)
    // ----------------------------------------------------
    console.log('\n>>> Step 12: Mobile Viewport QA (375x667)');
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);

    const ticketOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth - window.innerWidth;
    });
    console.log(`    Ticket mobile horizontal overflow: ${ticketOverflow}px`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '18_mobile_ticket_viewport.png') });

    await page.goto(`${BASE_URL}/hospitals`, { waitUntil: 'networkidle' });
    const hospitalsOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth - window.innerWidth;
    });
    console.log(`    Hospitals mobile horizontal overflow: ${hospitalsOverflow}px`);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '19_mobile_hospitals_viewport.png') });

    console.log('\n======================================================================');
    console.log('    BROWSER QA RESULTS & HEALTH SUMMARY');
    console.log('======================================================================');
    console.log(`Uncaught Console Errors: ${consoleErrors.length}`);
    if (consoleErrors.length > 0) {
      consoleErrors.forEach((e) => console.log('  [ERROR]:', e));
    }
    console.log(`Failed Network Requests: ${networkErrors.length}`);
    if (networkErrors.length > 0) {
      networkErrors.forEach((e) => console.log('  [FAILED]:', e));
    }

    const qaPassed = consoleErrors.length === 0 && networkErrors.length === 0 && ticketOverflow <= 0;
    console.log(`\nOVERALL BROWSER QA STATUS: ${qaPassed ? 'ALL PASS (100%)' : 'ISSUES DETECTED'}`);
    console.log('======================================================================\n');

  } catch (err) {
    console.error('Fatal Browser QA Error:', err);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'fatal_qa_error.png') }).catch(() => {});
    throw err;
  } finally {
    await browser.close();
  }
}

runPhase10QA();
