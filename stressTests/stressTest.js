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
        "user_selections": [
            {"column_name": "birdth", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "email", "is_quasi_identifier": true, "should_anonymize": true},
            {"column_name": "alias", "is_quasi_identifier": false, "should_anonymize": false}
        ] 
    }
];

// ==== STRESS TEST ====
export let options = {
  stages: [
    { duration: '5m', target: 50 },   // 50 users in 5 mins
    { duration: '5m', target: 100 },  // up to 100 users
    { duration: '5m', target: 150 },  // up to 150 users
    { duration: '5m', target: 200 },  // up to 200 users
    { duration: '4m', target: 0 },    // stop
  ],
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
        
        // Handle rate limiting (429 Too Many Requests)
        if (res.status === 429) {
            console.warn(`Rate limited for job ${job_id} - waiting longer before retry`);
            sleep(3 + Math.random() * 2); // Wait 3-5 seconds for rate limiting
            count++;
            continue;
        }
        
        // Check if response is successful before parsing
        if (res.status !== 200) {
            console.warn(`Status check failed for job ${job_id}: HTTP ${res.status} - ${res.body}`);
            sleep(1 + Math.random());
            count++;
            continue;
        }
        
        try {
            let body = res.json();
            status = body.status;
            
            console.log(`Job ${job_id} - Status: ${status} (poll ${count + 1}/${maxPolls})`);
            
            if (status === desired_status) {
                return status;
            }
            
            if (status === 'error') {
                // Better error logging
                let errorMsg = typeof body.error === 'string' ? body.error : JSON.stringify(body.error || body);
                fail(`Job ${job_id} failed with error: ${errorMsg}`);
            }
            
        } catch (e) {
            console.error(`Failed to parse JSON response for job ${job_id}: ${e.message}`);
            console.error(`Response status: ${res.status}`);
            console.error(`Response body: ${res.body.substring(0, 500)}...`); // Log first 500 chars
            
            // If it's a parsing error, might be temporary server issue
            if (count < maxPolls - 1) {
                console.log(`Retrying in 2 seconds...`);
                sleep(2);
                count++;
                continue;
            } else {
                fail(`Persistent JSON parsing error for job ${job_id}: ${e.message}`);
            }
        }
        
        sleep(1 + Math.random()); // random wait between 1 and 2 sec
        count++;
    }
    
    fail(`Timeout: Job ${job_id} did not reach status '${desired_status}' after ${maxPolls} polls`);
}

export default function () {
    let job_id;

    // 1) File upload
    let formData = {
        file: http.file(fileData, 'testFile.csv'),
    };
    let uploadRes = http.post(`${BASE_URL}/noauth_upload_and_analyze`, formData);
    
    if (!check(uploadRes, { 'upload ok': (r) => r.status === 202 })) {
        console.error(`Upload failed: HTTP ${uploadRes.status} - ${uploadRes.body}`);
        return; // Exit early if upload fails
    }

    // 2) Extract job_id
    try {
        let uploadBody = uploadRes.json();
        job_id = uploadBody.job_id;
        
        if (!job_id) {
            fail(`job_id is undefined. Response body: ${JSON.stringify(uploadBody)}`);
        }
        
        check(job_id, { 'job_id exists': (j) => !!j });
        console.log(`Created job: ${job_id}`);
        
    } catch (e) {
        fail(`Failed to parse upload response: ${e.message}. Response: ${uploadRes.body}`);
    }

    // 3-4) Polling until status === "analyzed"
    let analyzed = pollStatus(job_id, 'analyzed');
    check(analyzed, { 'status is analyzed': (s) => s === 'analyzed' });

    // 5) POST to /request_anonymization with one of the 3 random payloads
    let anonPayload = anonymizationPayloads[Math.floor(Math.random() * anonymizationPayloads.length)];
    anonPayload["job_id"] = job_id;
    
    let anonRes = http.post(`${BASE_URL}/noauth_request_anonymization`, JSON.stringify(anonPayload), {
        headers: { 'Content-Type': 'application/json' },
    });
    
    if (!check(anonRes, { 'anonymization request ok': (r) => r.status === 202 })) {
        console.error(`Anonymization request failed: HTTP ${anonRes.status} - ${anonRes.body}`);
        return; // Exit early if anonymization request fails
    }

    // 6-7) Polling until status === "anonymized"
    let anonymized = pollStatus(job_id, 'anonymized');
    check(anonymized, { 'status is anonymized': (s) => s === 'anonymized' });

    // 8) Download result
    let downloadRes = http.get(`${BASE_URL}/noauth_download/${job_id}`);
    
    if (!check(downloadRes, { 'download ok': (r) => r.status === 200 })) {
        console.error(`Download failed: HTTP ${downloadRes.status} - ${downloadRes.body}`);
        return;
    }
    
    console.log(`Job ${job_id} completed successfully`);
    sleep(Math.random() * 2 + 1);
}