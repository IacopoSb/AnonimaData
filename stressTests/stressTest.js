import http from 'k6/http';
import { check, sleep } from 'k6';

// The 3 possible payloads for the anonymization request
const anonymizationPayloads = [
    { "param1": "value1a", "param2": "value2a" },
    { "param1": "value1b", "param2": "value2b" },
    { "param1": "value1c", "param2": "value2c" }
];

// ==== STRESS TEST ====
export let options = {
  stages: [
    { duration: '5m', target: 50 },   // 50 users in 2 mins
    { duration: '5m', target: 100 },  // up to 100 users
    { duration: '5m', target: 200 },  // up to 200 users
    { duration: '5m', target: 400 },  // up to 400 users
    { duration: '4m', target: 0 },    // stop
  ],
};

const BASE_URL = 'https://';

// Polling function for status
function pollStatus(job_id, desired_status) {
    let status = '';
    let maxPolls = 60; // safety timeout (1min with sleep 1s)
    let count = 0;
    while (count < maxPolls) {
        let res = http.get(`${BASE_URL}/get_status/${job_id}`);
        if (res.status !== 200) break;
        let body = res.json();
        status = body.status;
        if (status === desired_status) break;
        sleep(1 + Math.random()); // random wait between 1 and 2 sec
        count++;
    }
    return status;
}

export default function () {
    // 1) File upload
    let fileData = open('./testFile.csv', 'b'); // Load a local sample file
    let uploadRes = http.post(`${BASE_URL}/upload_and_analyze`, fileData, {
        headers: { 'Content-Type': 'application/octet-stream' },
    });
    check(uploadRes, { 'upload ok': (r) => r.status === 200 });

    // 2) Extract job_id
    let job_id = uploadRes.json('job_id');
    check(job_id, { 'job_id exists': (j) => !!j });

    // 3-4) Polling until status === "analyzed"
    let analyzed = pollStatus(job_id, 'analyzed');
    check(analyzed, { 'status is analyzed': (s) => s === 'analyzed' });

    // 5) POST to /request_anonymization with one of the 3 random payloads
    let anonPayload = anonymizationPayloads[Math.floor(Math.random() * anonymizationPayloads.length)];
    anonPayload["job_id"] = job_id;
    let anonRes = http.post(`${BASE_URL}/request_anonymization`, JSON.stringify(anonPayload), {
        headers: { 'Content-Type': 'application/json' },
    });
    check(anonRes, { 'anonymization request ok': (r) => r.status === 200 });

    // 6-7) Polling until status === "anonymized"
    let anonymized = pollStatus(job_id, 'anonymized');
    check(anonymized, { 'status is anonymized': (s) => s === 'anonymized' });

    // 8) Download result
    let downloadRes = http.get(`${BASE_URL}/download/${job_id}`);
    check(downloadRes, { 'download ok': (r) => r.status === 200 });

    sleep(Math.random() * 2 + 1);
}