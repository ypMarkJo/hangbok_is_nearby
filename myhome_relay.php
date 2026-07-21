<?php
/**
 * myhome_relay.php
 * 
 * PHP Relay Script for proxying requests from GitHub Actions to myhome.go.kr
 * Deployed on Dothome hosting server (woojoo720.dothome.co.kr).
 */

// Enable CORS headers for cross-origin requests
header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: POST, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Authorization, X-Requested-With");

// Handle preflight OPTIONS request
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// Simple authentication key
define('DEFAULT_API_KEY', 'hangbok_relay_2026');

// Read JSON payload from input stream
$raw_input = file_get_contents('php://input');
$data = json_decode($raw_input, true);

if (!is_array($data)) {
    header('Content-Type: application/json');
    http_response_code(400);
    echo json_encode(['error' => 'Invalid JSON input']);
    exit;
}

// 1. API Key Authentication
$provided_key = isset($data['api_key']) ? (string)$data['api_key'] : '';
if (!hash_equals(DEFAULT_API_KEY, $provided_key)) {
    header('Content-Type: application/json');
    http_response_code(401);
    echo json_encode(['error' => 'unauthorized']);
    exit;
}

$action = isset($data['action']) ? (string)$data['action'] : '';
$params = (isset($data['params']) && is_array($data['params'])) ? $data['params'] : [];

$user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

switch ($action) {
    case 'list':
        // POST to list endpoint
        $url = 'https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcList.do';
        $post_data = http_build_query($params);

        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $post_data,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 15,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/x-www-form-urlencoded; charset=UTF-8',
                'Referer: https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcView.do',
                'X-Requested-With: XMLHttpRequest',
                'User-Agent: ' . $user_agent
            ]
        ]);

        $response = curl_exec($ch);
        $err = curl_error($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($response === false || $http_code >= 400) {
            header('Content-Type: application/json');
            http_response_code(502);
            echo json_encode(['error' => $err ? $err : "HTTP status code " . $http_code]);
            exit;
        }

        header('Content-Type: application/json');
        echo $response;
        break;

    case 'detail':
        // GET detail endpoint
        $pblanc_id = isset($params['pblancId']) ? $params['pblancId'] : '';
        if (empty($pblanc_id)) {
            header('Content-Type: application/json');
            http_response_code(400);
            echo json_encode(['error' => 'Missing required parameter: pblancId']);
            exit;
        }

        $url = 'https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId=' . urlencode($pblanc_id);

        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 15,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_HTTPHEADER => [
                'User-Agent: ' . $user_agent
            ]
        ]);

        $response = curl_exec($ch);
        $err = curl_error($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($response === false || $http_code >= 400) {
            header('Content-Type: application/json');
            http_response_code(502);
            echo json_encode(['error' => $err ? $err : "HTTP status code " . $http_code]);
            exit;
        }

        header('Content-Type: text/html; charset=UTF-8');
        echo $response;
        break;

    case 'pdf':
        // GET PDF download endpoint
        $atch_file_id = isset($params['atchFileId']) ? $params['atchFileId'] : '';
        $file_sn = isset($params['fileSn']) ? $params['fileSn'] : '1';

        if (empty($atch_file_id)) {
            header('Content-Type: application/json');
            http_response_code(400);
            echo json_encode(['error' => 'Missing required parameter: atchFileId']);
            exit;
        }

        $url = 'https://www.myhome.go.kr/hws/com/fms/cvplFileDownload.do?atchFileId=' . urlencode($atch_file_id) . '&fileSn=' . urlencode($file_sn);

        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_HTTPHEADER => [
                'User-Agent: ' . $user_agent
            ]
        ]);

        $response = curl_exec($ch);
        $err = curl_error($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($response === false || $http_code >= 400) {
            header('Content-Type: application/json');
            http_response_code(502);
            echo json_encode(['error' => $err ? $err : "HTTP status code " . $http_code]);
            exit;
        }

        header('Content-Type: application/json');
        echo json_encode([
            'status' => 'ok',
            'data' => base64_encode($response),
            'content_type' => 'application/pdf'
        ]);
        break;

    default:
        header('Content-Type: application/json');
        http_response_code(400);
        echo json_encode(['error' => 'invalid action']);
        break;
}
