import http from 'k6/http';
import { check, sleep, fail } from 'k6';

// The 3 possible payloads for the anonymization request
const anonymizationPayloads = [
    {
        "method": "differential-privacy",
        "params": {
            "epsilon": 0.5
        },
        "user_selections": [
            {"column_name": "birdth", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "email", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "alias", "is_quasi_identifier": false, "should_anonymize": false}
        ]
    },
    { 
        "method": "l-diversity",
        "params": {
            "k": 4,
            "l": 2
        },
        "user_id": "user-def",
        "user_selections": [
            {"column_name": "birdth", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "email", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "alias", "is_quasi_identifier": false, "should_anonymize": false}
        ]
     },
    { 
        "method": "k-anonymity",
        "params": {
            "k": 5
        },
        "user_id": "user-abc",
        "user_selections": [
            {"column_name": "birdth", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "email", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "alias", "is_quasi_identifier": false, "should_anonymize": false}
        ] 
    }
];

// ==== SOAK TEST ====
export let options = {
    vus: 50,               // 50 users
    duration: '1h',        // 1 hour
};


const fileData = open('./testFile.csv', 'b');
const BASE_URL = 'https://orchestratore-sktg2ckwoq-ew.a.run.app';

// Polling function for status
function pollStatus(job_id, desired_status) {
    let status = '';
    let maxPolls = 120; // safety timeout (2min with sleep 1s)
    let count = 0;
    while (count < maxPolls) {
        let res = http.get(`${BASE_URL}/noauth_get_status/${job_id}`);
        let body = res.json();
        status = body.status;
        if (status === desired_status) break;
        if (status === 'error') {
            fail(`Job ${job_id} failed with error: ${body}`);
        }
        sleep(1 + Math.random()); // random wait between 1 and 2 sec
        count++;
    }
    return status;
}

export default function () {
    let job_id;
    try {
        // 1) File upload
        let formData = {
            file: http.file(fileData, 'testFile.csv'),
        };
        let uploadRes = http.post(`${BASE_URL}/noauth_upload_and_analyze`, formData);
        check(uploadRes, { 'upload ok': (r) => r.status === 202 });

        // 2) Extract job_id
        job_id = uploadRes.json('job_id');
        if (!job_id) {
            fail('job_id is undefined: response body: ' + JSON.stringify(uploadRes.json()));
        }
        check(job_id, { 'job_id exists': (j) => !!j });

        // 3-4) Polling until status === "analyzed"
        let analyzed = pollStatus(job_id, 'analyzed');
        check(analyzed, { 'status is analyzed': (s) => s === 'analyzed' });

        // 5) POST to /request_anonymization with one of the 3 random payloads
        let anonPayload = anonymizationPayloads[Math.floor(Math.random() * anonymizationPayloads.length)];
        anonPayload["job_id"] = job_id;
        let anonRes = http.post(`${BASE_URL}/noauth_request_anonymization`, JSON.stringify(anonPayload), {
            headers: { 'Content-Type': 'application/json' },
        });
        check(anonRes, { 'anonymization request ok': (r) => r.status === 202 });

        // 6-7) Polling until status === "anonymized"
        let anonymized = pollStatus(job_id, 'anonymized');
        check(anonymized, { 'status is anonymized': (s) => s === 'anonymized' });

        // 8) Download result
        let downloadRes = http.get(`${BASE_URL}/noauth_download/${job_id}`);
        check(downloadRes, { 'download ok': (r) => r.status === 200 });

        sleep(Math.random() * 2 + 1);
    } finally {
        // Cleanup: always call delete
        if (job_id) {
            http.del(`${BASE_URL}/delete/${job_id}`);
        }
    }
}