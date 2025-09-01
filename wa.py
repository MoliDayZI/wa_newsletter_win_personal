from flask import Flask, render_template_string, request, jsonify, session
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import threading
import time
import io
import traceback
import os
import uuid
import re
import random
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', '631817fd2b7423dbda6ed9ff8ab254522cab62cc947ca326b714c12a7385e139')

user_contexts = {}

def get_uid():
    if 'uid' not in session:
        session['uid'] = str(uuid.uuid4())
    return session['uid']

def get_ctx():
    uid = get_uid()
    if uid not in user_contexts:
        user_contexts[uid] = {
            'driver': None,
            'progress_list': [],
            'stop_flag': False,
            'session_active': False,
            'sending_flag': False,
            'logs': [],
            'failed_numbers': [],
            'success_count': 0,
            'failed_count': 0
        }
    return uid, user_contexts[uid]

HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WhatsApp рассылка</title>
  <meta name="description" content="Удобная веб‑панель для массовой отправки сообщений в WhatsApp: загрузка Excel, текст и изображения, многопользовательские сессии, сохранение входа.">
  <meta name="keywords" content="WhatsApp, рассылка, массовые сообщения, WhatsApp Web, Excel, маркетинг">
  <meta name="robots" content="index, follow">
  <meta name="theme-color" content="#25d366">

  <!-- Open Graph -->
  <meta property="og:title" content="WhatsApp рассылка">
  <meta property="og:description" content="Массовая отправка сообщений через WhatsApp Web. Импорт номеров из Excel, подписи к изображениям, прогресс и отчёт.">
  <meta property="og:type" content="website">
  <meta property="og:image" content="https://static.whatsapp.net/rsrc.php/v3/yV/r/_-QK4QpCml_.png">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="WhatsApp рассылка">
  <meta name="twitter:description" content="Импорт из Excel, текст/изображения, прогресс, многопользовательские сессии.">
  <meta name="twitter:image" content="https://static.whatsapp.net/rsrc.php/v3/yV/r/_-QK4QpCml_.png">

  <link rel="icon" href="https://static.whatsapp.net/rsrc.php/v3/yV/r/_-QK4QpCml_.png">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css" rel="stylesheet">
  <style>
    body {
      background: linear-gradient(180deg, #e8f5e9 0%, #f0f2f5 40%, #f7f9fb 100%);
      min-height: 100vh;
    }
    .app-header {
      background: #25d366;
      color: #fff;
      border-radius: 1rem;
      padding: 1.25rem 1.5rem;
      box-shadow: 0 8px 18px rgba(37, 211, 102, 0.25);
    }
    .card {
      border: none;
      border-radius: 1rem;
      box-shadow: 0 8px 22px rgba(0,0,0,0.06);
    }
    .card .card-title { font-weight: 600; }
    #progress-box { max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 0.92em; }
    .qr-box { text-align:center; }
    .qr-box img { border: 1px solid #e6e6e6; border-radius: .75rem; padding: 8px; background: #fff; }
    .status-label { font-weight: 600; }
    .btn-success { background-color: #25d366; border-color: #22c25c; }
    .btn-success:hover { background-color: #20b957; border-color: #1ea651; }
    .btn-primary { background-color: #128c7e; border-color: #0f7a6d; }
    .btn-primary:hover { background-color: #0f7a6d; border-color: #0d6b60; }
    .contact-link { text-decoration: none; }
    .contact-link .bi { font-size: 1.25rem; }
    .contact-card .list-group-item { border: none; }
  </style>
</head>
<body>
<div class="container py-4">
  <div class="app-header mb-4 d-flex align-items-center justify-content-between">
    <h1 class="h4 m-0 d-flex align-items-center gap-2"><i class="bi bi-whatsapp"></i> WhatsApp рассылка</h1>
    <div class="small opacity-75">Многопользовательские сессии • Сохранение входа</div>
  </div>

  <!-- Сессия -->
  <div class="card mb-4">
    <div class="card-body">
      <h5 class="card-title"><i class="bi bi-box-arrow-in-right"></i> Подключение к WhatsApp Web</h5>
      <p class="card-text">Сначала откройте WhatsApp Web, отсканируйте QR-код, который появится ниже, и дождитесь подтверждения входа. Лучше всего использовать сервис на ПК, чтобы с телефона отсканировать QR.</p>
      <button id="btn-qr" class="btn btn-primary"><i class="bi bi-qr-code-scan"></i> Открыть WhatsApp Web</button>
      <span id="status" class="ms-3 status-label text-muted"></span>
      <div class="qr-box mt-3">
        <img id="qr-image" src="" alt="QR для WhatsApp" style="max-width:220px; display:none;">
      </div>
    </div>
  </div>

  <!-- Форма рассылки -->
  <div class="card mb-4">
    <div class="card-body">
      <h5 class="card-title"><i class="bi bi-envelope-paper"></i> Настройка рассылки</h5>
      <form id="send-form" enctype="multipart/form-data">
        <div class="mb-3">
          <label for="file" class="form-label">📂 Excel с номерами (.xlsx)</label>
          <input class="form-control" type="file" id="file" name="file" required accept=".xlsx">
          <div class="form-text">
            Требуется файл Excel с колонкой <code>phone</code>, где под ней идут номера в формате
            <code>+79XXXXXXXXX</code> (без пробелов и тире).
          </div>
        </div>
        <div class="mb-3">
          <label for="message" class="form-label">✍️ Сообщение</label>
          <textarea class="form-control" id="message" name="message" rows="4" placeholder="Введите текст рассылки..."></textarea>
        </div>
        <div class="mb-3">
          <label for="image" class="form-label">🖼️ Изображение (опционально)</label>
          <input class="form-control" type="file" id="image" name="image" accept="image/*">
        </div>
        <div class="mb-3">
            <label class="form-label">⏱ Интервал между сообщениями (секунды)</label>
            <div class="d-flex gap-2">
                <input type="number" class="form-control" id="interval_min" name="interval_min" value="10" min="1" required>
                <span class="align-self-center">до</span>
                <input type="number" class="form-control" id="interval_max" name="interval_max" value="30" min="1" required>
            </div>
            <div class="form-text">Для естественности: например 10–30 секунд</div>
        </div>
        <div class="d-flex gap-2">
          <button type="submit" class="btn btn-success" id="btn-send" disabled><i class="bi bi-send-check"></i> Запустить</button>
          <button type="button" class="btn btn-danger" id="btn-stop" disabled><i class="bi bi-stop-circle"></i> Остановить</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Прогресс -->
  <div class="card">
    <div class="card-body">
      <h5 class="card-title"><i class="bi bi-graph-up"></i> Прогресс рассылки</h5>
      <div id="progress-box" class="border bg-light p-2 rounded mb-3"></div>
      <div class="progress">
        <div id="progress-bar" class="progress-bar progress-bar-striped progress-bar-animated bg-success" role="progressbar" style="width: 0%">0%</div>
      </div>
      <div class="mt-3">
        <button type="button" class="btn btn-info" id="btn-report" disabled>
          <i class="bi bi-file-earmark-text"></i> Показать финальный отчет
        </button>
      </div>
    </div>
  </div>

  <!-- Финальный отчет -->
  <div class="card mt-4" id="report-card" style="display: none;">
    <div class="card-body">
      <h5 class="card-title"><i class="bi bi-clipboard-data"></i> Финальный отчет</h5>
      <div id="report-content"></div>
    </div>
  </div>

  <!-- Контакты для помощи -->
  <div class="card mt-4 contact-card">
    <div class="card-body">
      <h5 class="card-title mb-3"><i class="bi bi-life-preserver"></i> Нужна помощь?</h5>
      <p class="text-muted mb-3">Пишите, если возникли сложности — отвечу максимально быстро.</p>
      <div class="d-flex flex-wrap gap-2">
        <a class="btn btn-outline-primary contact-link" href="https://t.me/slnt_andy" target="_blank" rel="noopener">
          <i class="bi bi-telegram"></i> Telegram: @slnt_andy
        </a>
        <a class="btn btn-outline-success contact-link" href="https://wa.me/79082144730" target="_blank" rel="noopener">
          <i class="bi bi-whatsapp"></i> WhatsApp: +7 908 214-47-30
        </a>
        <a class="btn btn-outline-secondary contact-link" href="https://m.vk.com/slnt_andy" target="_blank" rel="noopener">
          <i class="bi bi-person-lines-fill"></i> VK: @slnt_andy
        </a>
      </div>
    </div>
  </div>
</div>

<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script>
let sessionActive = false;
let sending = false;
let totalNumbers = 0;

function updateProgress(){
    // Обновляем прогресс
    $.get('/progress', function(data){
        $('#progress-box').empty();
        totalNumbers = data.total;
        let sentCount = 0;
        let failedCount = 0;
        
        data.status.forEach(item => {
            let color = item.sent ? 'green' : item.current ? 'orange' : 'black';
            let status = item.sent ? '✅' : item.current ? '⏳' : '❌';
            $('#progress-box').append(`<div style="color:${color}">${item.number} - ${status}</div>`);
            
            if(item.sent) sentCount++;
            else if(!item.current) failedCount++;
        });
        
        let percent = totalNumbers > 0 ? Math.floor((sentCount/totalNumbers)*100) : 0;
        $('#progress-bar').css('width', percent+'%').text(`${percent}% (${sentCount}/${totalNumbers})`);
        
        // Показываем краткую статистику
        if(totalNumbers > 0) {
            $('#progress-box').prepend(`<div class="mb-2 p-2 bg-light rounded"><strong>Статистика:</strong> ✅ ${sentCount} | ❌ ${failedCount} | ⏳ ${totalNumbers - sentCount - failedCount}</div>`);
        }
    });

    // Проверяем, закончена ли рассылка
    $.get('/status', function(data){
        if(!data.sending){ // Если рассылка на сервере завершена
            if(sending){ // И если на фронте она считалась активной
                $('#status').text('Рассылка завершена');
                sending = false;
                $('#btn-send').prop('disabled', false);
                $('#btn-stop').prop('disabled', true);
                $('#btn-report').prop('disabled', false); // Активируем кнопку отчета
            }
        }
    });
}

function updateQR(){
    $.get('/qr', function(data){
        if(data.success && data.qr){
            $("#qr-image").attr("src", "data:image/png;base64," + data.qr).show();
        }
    });
}

function checkLogin(){
    $.get('/login_status', function(data){
        if(data.success && data.logged_in){
            $("#qr-image").hide();
            $("#status").text("✅ Вы успешно вошли");
            $("#btn-send").prop("disabled", false);
        }
    });
}

// Запрашиваем каждые 5 секунд
setInterval(checkLogin, 5000);

// Запрашивать QR каждые 5 секунд
setInterval(updateQR, 5000);

$('#btn-qr').click(function(){
    $('#status').text('Открытие WhatsApp Web...');
    $.post('/start_session', function(data){
        if(data.success){
            sessionActive = true;
            $('#status').text('WhatsApp Web открыт, отсканируйте QR-код в новом окне');
            $('#btn-send').prop('disabled', false);
        } else {
            $('#status').text('Ошибка при запуске сессии');
        }
    });
});

$('#send-form').submit(function(e){
    e.preventDefault();
    if(!sessionActive){
        alert('Сначала откройте и отсканируйте WhatsApp Web!');
        return;
    }
    if(sending){
        alert('Рассылка уже запущена!');
        return;
    }

    let formData = new FormData(this);
    $('#btn-send').prop('disabled', true);
    $('#btn-stop').prop('disabled', false);
    sending = true;
    $('#status').text('Запущена рассылка...');

    $.ajax({
        url: '/send',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(data){
            if(!data.success){
                $('#status').text('Ошибка: ' + data.error);
                sending = false;
                $('#btn-send').prop('disabled', false);
                $('#btn-stop').prop('disabled', true);
            }
        },
        error: function(){
            $('#status').text('Ошибка при запуске рассылки');
            sending = false;
            $('#btn-send').prop('disabled', false);
            $('#btn-stop').prop('disabled', true);
        }
    });
});

// Обновление прогресса и статуса каждые 2 секунды
setInterval(updateProgress, 2000);

// Автоматическое обновление отчета каждые 5 секунд после завершения рассылки
setInterval(function(){
    if(!sending && $('#btn-report').is(':enabled')) {
        // Если рассылка завершена и кнопка отчета активна, обновляем отчет
        $.get('/final_report', function(data){
            if(data.success){
                const report = data.report;
                let reportHtml = `
                    <div class="row">
                        <div class="col-md-6">
                            <h6 class="text-success">✅ Успешно отправлено: ${report.success_count}</h6>
                            <h6 class="text-danger">❌ Неуспешно: ${report.failed_count}</h6>
                            <h6 class="text-primary">📊 Общий процент успеха: ${report.success_rate}%</h6>
                        </div>
                        <div class="col-md-6">
                            <h6 class="text-info">📱 Всего номеров: ${report.total_numbers}</h6>
                        </div>
                    </div>
                `;
                
                if(report.failed_numbers && report.failed_numbers.length > 0){
                    reportHtml += `
                        <div class="mt-3">
                            <h6 class="text-danger">📋 Неуспешные номера:</h6>
                            <div class="border bg-light p-2 rounded" style="max-height: 200px; overflow-y: auto;">
                                ${report.failed_numbers.map(num => `<div class="text-danger">${num}</div>`).join('')}
                            </div>
                        </div>
                    `;
                }
                
                $('#report-content').html(reportHtml);
                $('#report-card').show();
            }
        });
    }
}, 5000);

$('#btn-stop').click(function(){
    $.post('/stop', function(data){
        if(data.success){
            $('#status').text('Рассылка остановлена');
            sending = false;
            $('#btn-send').prop('disabled', false);
            $('#btn-stop').prop('disabled', true);
        }
    });
});

// Кнопка показа отчета
$('#btn-report').click(function(){
    $.get('/final_report', function(data){
        if(data.success){
            const report = data.report;
            let reportHtml = `
                <div class="row">
                    <div class="col-md-6">
                        <h6 class="text-success">✅ Успешно отправлено: ${report.success_count}</h6>
                        <h6 class="text-danger">❌ Неуспешно: ${report.failed_count}</h6>
                        <h6 class="text-primary">📊 Общий процент успеха: ${report.success_rate}%</h6>
                    </div>
                    <div class="col-md-6">
                        <h6 class="text-info">📱 Всего номеров: ${report.total_numbers}</h6>
                    </div>
                </div>
            `;
            
            if(report.failed_numbers && report.failed_numbers.length > 0){
                reportHtml += `
                    <div class="mt-3">
                        <h6 class="text-danger">📋 Неуспешные номера:</h6>
                        <div class="border bg-light p-2 rounded" style="max-height: 200px; overflow-y: auto;">
                            ${report.failed_numbers.map(num => `<div class="text-danger">${num}</div>`).join('')}
                        </div>
                    </div>
                `;
            }
            
            $('#report-content').html(reportHtml);
            $('#report-card').show();
        } else {
            alert('Отчет пока недоступен: ' + data.message);
        }
    });
});
</script>
</body>
</html>
"""

def log(msg):
    print(msg)

def run_whatsapp_session(uid):
    uid_ctx = user_contexts.get(uid)
    if uid_ctx is None:
        return
    try:
        # Ensure persistent Chrome user profile per uid (keeps WhatsApp login)
        profiles_root = os.path.abspath(os.path.join(os.getcwd(), 'profiles'))
        os.makedirs(profiles_root, exist_ok=True)
        profile_dir = os.path.join(profiles_root, uid)
        os.makedirs(profile_dir, exist_ok=True)

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        # Optional: avoid automation banners
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) 
        chrome_options.add_experimental_option('useAutomationExtension', False)

        uid_ctx['driver'] = webdriver.Chrome(options=chrome_options)
        uid_ctx['driver'].get("https://web.whatsapp.com")
        uid_ctx['session_active'] = True
        log("WhatsApp Web открыт. Отсканируйте QR-код.")
    except Exception as e:
        log(f"Ошибка запуска браузера: {e}")
        uid_ctx['session_active'] = False

def send_messages_legacy(df, message):
    # Legacy function retained for reference; not used in multi-user mode
    pass

@app.route('/')
def index():
    return render_template_string(HTML)

def close_session(uid):
    uid_ctx = user_contexts.get(uid)
    if not uid_ctx:
        return
    driver = uid_ctx.get('driver')
    if driver:
        try:
            driver.quit()
            log("Браузер закрыт.")
        except:
            pass
        uid_ctx['driver'] = None
    uid_ctx['session_active'] = False

@app.route('/qr')
def get_qr():
    uid, ctx = get_ctx()
    driver = ctx.get('driver')
    if not driver:
        return jsonify(success=False, error="Браузер не запущен")

    try:
        # Находим canvas с QR
        canvas = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "canvas"))
        )
        # Получаем Base64 через JS
        qr_base64 = driver.execute_script(
            "return arguments[0].toDataURL('image/png').substring(22);", canvas
        )
        return jsonify(success=True, qr=qr_base64)
    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route('/login_status')
def login_status():
    uid, ctx = get_ctx()
    driver = ctx.get('driver')
    if not driver:
        return jsonify(success=False, logged_in=False, error="Браузер не запущен")
    try:
        # Проверяем, загрузился ли интерфейс чатов
        driver.find_element(By.XPATH, "//div[@role='grid']")  

        # Пробуем найти кнопку "Продолжить"
        try:
            continue_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[.//div[text()='Продолжить']]"
                ))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", continue_btn)
            continue_btn.click()
        except Exception:
            pass  # если кнопки нет, просто игнорируем

        return jsonify(success=True, logged_in=True)
    except:
        return jsonify(success=True, logged_in=False)

@app.route('/start_session', methods=['POST'])
def start_session():
    uid, ctx = get_ctx()
    try:
        close_session(uid)
        # Сбрасываем счетчики и отчеты для новой сессии
        ctx['progress_list'] = []
        ctx['failed_numbers'] = []
        ctx['success_count'] = 0
        ctx['failed_count'] = 0
        ctx['logs'] = []
        threading.Thread(target=run_whatsapp_session, args=(uid,), daemon=True).start()
        return jsonify({'success': True, 'message': 'Сессия запущена'})
    except Exception as e:
        error_text = traceback.format_exc()
        ctx['logs'].append(f"Ошибка при запуске сессии:\n{error_text}")
        return jsonify({'success': False, 'message': 'Ошибка при запуске сессии', 'details': str(e)})

@app.route('/status')
def status():
    uid, ctx = get_ctx()
    return jsonify(sending=ctx.get('sending_flag', False), stopped=ctx.get('stop_flag', False))

@app.route('/send', methods=['POST'])
def send():
    uid, ctx = get_ctx()
    if not ctx.get('session_active'):
        return jsonify(success=False, error="Сессия WhatsApp не запущена")
    ctx['stop_flag'] = False

    if ctx.get('sending_flag'):
        return jsonify({"status": "already_sending"})

    ctx['sending_flag'] = True
    
    # Сбрасываем счетчики
    ctx['failed_numbers'] = []
    ctx['success_count'] = 0
    ctx['failed_count'] = 0

    file = request.files.get('file')
    message = request.form.get('message')
    image = request.files.get('image')
    interval_min = request.form.get('interval_min', type=int, default=10)
    interval_max = request.form.get('interval_max', type=int, default=30)

    if interval_min > interval_max:
        interval_min, interval_max = interval_max, interval_min

    if not file:
        return jsonify(success=False, error="Файл с номерами обязателен")

    if not message and not image:
        return jsonify(success=False, error="Укажите сообщение или изображение")

    image_path = None
    if image:
        image_path = os.path.abspath(f"temp_{int(time.time())}.png")
        image.save(image_path)

    try:
        in_memory_file = io.BytesIO(file.read())
        df = pd.read_excel(in_memory_file)
        if 'phone' not in df.columns:
            return jsonify(success=False, error="В Excel нет колонки 'phone'")
    except Exception as e:
        return jsonify(success=False, error=f"Ошибка чтения файла: {e}")

    threading.Thread(
        target=send_messages,
        args=(uid, df, message, image_path, interval_min, interval_max),
        daemon=True
    ).start()
    return jsonify(success=True)

def set_text_multiline(driver, element, text):
    lines = text.split('\n')
    for i, line in enumerate(lines):
        # Вставляем строку целиком (смайлы корректные)
        driver.execute_script("arguments[0].focus();", element)
        driver.execute_script("document.execCommand('insertText', false, arguments[0]);", line)
        
        # Если это не последняя строка → вставляем перенос (Shift+Enter)
        if i < len(lines) - 1:
            element.send_keys(Keys.SHIFT, Keys.ENTER)

def send_messages(uid, df, message, image_path=None, interval_min=10, interval_max=30):
    uid_ctx = user_contexts.get(uid)
    if uid_ctx is None:
        return
    driver = uid_ctx.get('driver')
    if driver is None:
        uid_ctx['sending_flag'] = False
        return

    def normalize_phone(raw_value):
        """Normalize various phone formats to international +<country><number>.
        Examples:
        - 8 916-017-71-38 -> +79160177138
        - 89160177138     -> +79160177138
        - 9160177138      -> +79160177138 (assume RU for 10-digit starting with 9)
        - +380667542304   -> +380667542304
        - 00380667542304  -> +380667542304
        """
        s_raw = str(raw_value).strip()
        if not s_raw:
            return None
        digits = re.sub(r"\D", "", s_raw)
        if not digits:
            return None

        had_plus = s_raw.strip().startswith('+')

        # Convert 00-prefix to international
        if digits.startswith('00'):
            digits = digits[2:]

        # Russia-specific normalizations
        if len(digits) == 11 and digits.startswith('8'):
            # 8XXXXXXXXXX -> +7XXXXXXXXXX
            return "+7" + digits[1:]
        if len(digits) == 10 and digits.startswith('9'):
            # 9XXXXXXXXX -> +79XXXXXXXXX
            return "+7" + digits
        if len(digits) == 11 and digits.startswith('7'):
            return "+" + digits

        # Ukraine example 380...
        if len(digits) == 12 and digits.startswith('380'):
            return "+" + digits

        # If original had '+', keep it
        if had_plus:
            return "+" + digits

        # Fallback: prefix '+' to whatever we have if plausible length
        return "+" + digits

    # Подготовка списка уникальных номеров (в порядке исходного файла)
    seen_numbers = set()
    unique_numbers = []
    for _, row in df.iterrows():
        raw = str(row['phone']).strip()
        # Пропускаем пустые/NaN/недигитные значения
        if not raw or raw.lower() in {"nan", "none"}:
            continue
        if re.sub(r"\D", "", raw) == "":
            continue
        normalized = normalize_phone(raw)
        if not normalized:
            continue
        if normalized in seen_numbers:
            continue
        seen_numbers.add(normalized)
        unique_numbers.append(normalized)

    # Инициализация прогресса и счетчиков по уникальным номерам
    uid_ctx['progress_list'] = [{
        'number': number,
        'sent': False,
        'current': False
    } for number in unique_numbers]
    uid_ctx['failed_numbers'] = []
    uid_ctx['success_count'] = 0
    uid_ctx['failed_count'] = 0

    # Рантайм-защита от повторной отправки в рамках одной сессии
    already_sent_numbers = set()

    for number in unique_numbers:
        if uid_ctx.get('stop_flag'):
            break

        # Пропускаем, если этот номер уже был успешно обработан ранее в этой сессии
        if number in already_sent_numbers:
            continue
        send_text = bool(message and message.strip())
        send_image = bool(image_path)

        # Отмечаем текущий номер
        for item in uid_ctx['progress_list']:
            item['current'] = (item['number'] == number)

        try:
            # 1. Дождаться, пока не исчезнут всплывающие окна (если есть)
            try:
                WebDriverWait(driver, 3).until_not(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@role, 'dialog')]"))
                )
            except Exception:
                pass

            # 2. Найти и кликнуть "Новый чат"
            new_chat_btn = WebDriverWait(driver, 20).until(
                EC.visibility_of_element_located((By.XPATH, "//span[@data-icon='new-chat-outline']/parent::*"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", new_chat_btn)
            try:
                new_chat_btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", new_chat_btn)

            # 3. Найти поле поиска и ввести номер (контент-редактируемое поле)
            search_xpaths = [
                # Точное соответствие метке с учетом неразрывных пробелов через normalize-space
                "//div[@role='textbox' and @contenteditable='true' and normalize-space(@aria-label)='Поиск по имени или номеру']",
                # Любая метка, содержащая слово 'Поиск'
                "//div[@role='textbox' and @contenteditable='true' and contains(@aria-label,'Поиск')]",
                # Частый вариант поля lexical editor
                "//div[@role='textbox' and @contenteditable='true' and @data-lexical-editor='true']",
                # Запасной вариант по вкладке
                "//div[contains(@data-tab,'3') and @contenteditable='true']",
                # Универсальный запасной вариант
                "//div[@role='textbox' and @contenteditable='true']"
            ]
            search_box = None
            for sx in search_xpaths:
                try:
                    search_box = WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.XPATH, sx))
                    )
                    break
                except Exception:
                    continue
            if not search_box:
                raise TimeoutException("Поле поиска нового чата не найдено")

            # Фокус и очистка поля
            try:
                WebDriverWait(driver, 5).until(EC.visibility_of(search_box))
                driver.execute_script("arguments[0].focus();", search_box)
                search_box.click()
            except Exception:
                pass

            # Надежная очистка contenteditable: Ctrl+A и Backspace
            try:
                search_box.send_keys(Keys.CONTROL, 'a')
                search_box.send_keys(Keys.BACK_SPACE)
            except Exception:
                pass

            # Вставка номера: сначала send_keys в сам элемент
            typed = False
            try:
                search_box.send_keys(number)
                typed = True
            except Exception:
                typed = False
            # Фоллбек: отправить в activeElement
            if not typed:
                try:
                    active = driver.switch_to.active_element
                    active.send_keys(number)
                    typed = True
                except Exception:
                    pass
            # Фоллбек через execCommand
            if not typed:
                try:
                    driver.execute_script("arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);", search_box, number)
                    typed = True
                except Exception:
                    pass

            # Даем время визуально увидеть набранный номер (минимальная пауза)
            time.sleep(0.1)

            # 4. Если отображается сообщение "Не найдено результатов" — очищаем поле и пропускаем номер
            try:
                nf_elem = WebDriverWait(driver, 0.5).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//span[contains(normalize-space(text()), 'Не найдено результатов для')]"
                    ))
                )
                if nf_elem:
                    try:
                        search_box.send_keys(Keys.CONTROL, 'a')
                        search_box.send_keys(Keys.BACK_SPACE)
                    except Exception:
                        pass
                    for item in uid_ctx['progress_list']:
                        if item['number'] == number:
                            item['current'] = False
                    uid_ctx['failed_numbers'].append(number)
                    uid_ctx['failed_count'] += 1
                    uid_ctx['logs'].append(f"Номер не найден в WhatsApp (нет результатов поиска): {number}")
                    time.sleep(0.1)
                    continue
            except Exception:
                pass

            # 5. Переход в чат: пробуем кликнуть результат с совпадающим номером, иначе жмем Enter
            clicked_result = False
            try:
                # Ждем появления списка результатов (минимальное ожидание)
                WebDriverWait(driver, 1).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//span[@title]"))
                )
                candidates = driver.find_elements(By.XPATH, "//span[@title]")
                target_digits = re.sub(r"\D", "", number)
                for cand in candidates:
                    try:
                        title = cand.get_attribute('title') or cand.text or ''
                        cand_digits = re.sub(r"\D", "", title)
                        if cand_digits == target_digits or cand_digits.endswith(target_digits):
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cand)
                            cand.click()
                            clicked_result = True
                            break
                    except Exception:
                        continue
            except Exception:
                clicked_result = False

            if not clicked_result:
                search_box.send_keys(Keys.ENTER)
                uid_ctx['logs'].append(f"Открываем чат (Enter) для: {number}")
                # Если чат не открылся быстро — повторим Enter ещё раз
                try:
                    WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, "//footer"))
                    )
                except Exception:
                    try:
                        search_box.send_keys(Keys.ENTER)
                        uid_ctx['logs'].append(f"Повторный Enter для открытия чата: {number}")
                    except Exception:
                        pass
            else:
                uid_ctx['logs'].append(f"Открываем чат (клик по результату) для: {number}")

            # 5. Дождаться открытия чата (если не открылся — номер не найден, пропускаем)
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//footer"))
                )
            except TimeoutException:
                # Чат не открылся — вероятно, номер не найден. Пропускаем.
                for item in uid_ctx['progress_list']:
                    if item['number'] == number:
                        item['current'] = False
                uid_ctx['failed_numbers'].append(number)
                uid_ctx['failed_count'] += 1
                uid_ctx['logs'].append(f"Номер не найден в WhatsApp: {number}")
                time.sleep(0.1)
                continue

            # 6. Отправка изображения
            if send_image:
                attach_btn = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@title='Прикрепить']"))
                )
                attach_btn.click()

                img_input = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@type='file' and contains(@accept, 'image')]"))
                )
                img_input.send_keys(image_path)

                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//img[@alt='Предпросмотр']"))
                )

                if send_text:
                    caption_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true' and @aria-label='Добавьте подпись']"))
                    )
                    caption_box.click()
                    set_text_multiline(driver, caption_box, message)

                # Кнопка отправки
                send_btn_xpaths = [
                    "//div[@role='button' and @aria-label='Отправить']",
                    "//button[@aria-label='Отправить']",
                    "//span[@data-icon='wds-ic-send-filled']/ancestor::div[@role='button']"
                ]
                send_img_btn = None
                for xpath in send_btn_xpaths:
                    try:
                        send_img_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        break
                    except Exception:
                        continue
                if send_img_btn:
                    driver.execute_script("arguments[0].scrollIntoView(true);", send_img_btn)
                    send_img_btn.click()

            # 7. Отправка текста
            elif send_text:
                input_xpaths = [
                    "//footer//div[@contenteditable='true' and contains(@aria-label,'Введите сообщение')]",
                    "//footer//div[@contenteditable='true' and @role='textbox']",
                    "//footer//div[@contenteditable='true' and @data-lexical-editor='true']",
                    "//footer//div[@contenteditable='true']"
                ]
                input_div = None
                for ix in input_xpaths:
                    try:
                        input_div = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, ix))
                        )
                        uid_ctx['logs'].append(f"Поле ввода найдено по селектору: {ix}")
                        break
                    except Exception:
                        continue
                if not input_div:
                    uid_ctx['logs'].append("Поле ввода сообщения не найдено")
                    raise TimeoutException("Поле ввода сообщения не найдено")

                try:
                    driver.execute_script("arguments[0].focus();", input_div)
                    input_div.click()
                except Exception:
                    pass

                set_text_multiline(driver, input_div, message)

                send_btn_candidates = [
                    "//footer//button[@aria-label='Отправить']",
                    "//footer//*[@role='button' and @aria-label='Отправить']",
                    "//footer//span[@data-icon='send']/ancestor::*[@role='button']",
                    "//footer//span[contains(@data-icon,'send')]/ancestor::*[@role='button']"
                ]
                clicked_send = False
                for sbx in send_btn_candidates:
                    try:
                        send_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, sbx))
                        )
                        driver.execute_script("arguments[0].scrollIntoView(true);", send_button)
                        send_button.click()
                        uid_ctx['logs'].append(f"Отправка через кнопку: {sbx}")
                        clicked_send = True
                        break
                    except Exception:
                        continue
                if not clicked_send:
                    uid_ctx['logs'].append("Кнопка отправки не найдена, отправляю Enter")
                    input_div.send_keys(Keys.ENTER)
                time.sleep(0.6)

            # После успешной отправки отмечаем в прогрессе
            for item in uid_ctx['progress_list']:
                if item['number'] == number:
                    item['sent'] = True
                    item['current'] = False
            uid_ctx['success_count'] += 1
            already_sent_numbers.add(number)

        except Exception as e:
            # Если ошибка — отмечаем как неуспешный
            for item in uid_ctx['progress_list']:
                if item['number'] == number:
                    item['current'] = False
            uid_ctx['failed_numbers'].append(number)
            uid_ctx['failed_count'] += 1
            # Логируем ошибку
            uid_ctx['logs'].append(f"Ошибка отправки на номер {number}: {str(e)}")

        if not uid_ctx.get('stop_flag'):
            if interval_min == interval_max:
                pause = interval_min
            else:
                pause = random.uniform(interval_min, interval_max)
            uid_ctx['logs'].append(f"⏱ Пауза {pause:.1f} сек.")
            time.sleep(pause)

    # Генерируем финальный отчет
    total_numbers = len(uid_ctx['progress_list'])
    success_rate = (uid_ctx['success_count'] / total_numbers * 100) if total_numbers > 0 else 0
    
    uid_ctx['logs'].append(f"""
=== ФИНАЛЬНЫЙ ОТЧЕТ ===
Всего номеров: {total_numbers}
Успешно отправлено: {uid_ctx['success_count']}
Неуспешно: {uid_ctx['failed_count']}
Процент успеха: {success_rate:.1f}%

Неуспешные номера:
{chr(10).join(uid_ctx['failed_numbers']) if uid_ctx['failed_numbers'] else 'Нет'}
=======================
""")

    uid_ctx['sending_flag'] = False
    uid_ctx['stop_flag'] = False
    
    # Очистка временного изображения
    if image_path:
        try:
            os.remove(image_path)
        except:
            pass
    
    # Закрыть браузер по завершению рассылки
    try:
        close_session(uid)
    except Exception:
        pass

@app.route('/progress')
def progress():
    uid, ctx = get_ctx()
    progress_list = ctx.get('progress_list', [])
    sent_count = sum(1 for x in progress_list if x.get('sent'))
    return jsonify(total=len(progress_list), sent_count=sent_count, status=progress_list)

@app.route('/stop', methods=['POST'])
def stop():
    uid, ctx = get_ctx()
    ctx['stop_flag'] = True
    return jsonify(success=True)

@app.route('/logs')
def get_logs():
    uid, ctx = get_ctx()
    return "\n".join(ctx.get('logs', []))

@app.route('/final_report')
def get_final_report():
    uid, ctx = get_ctx()
    if not ctx.get('sending_flag') and ctx.get('progress_list'):
        # Рассылка завершена, возвращаем финальный отчет
        total_numbers = len(ctx.get('progress_list', []))
        success_count = ctx.get('success_count', 0)
        failed_count = ctx.get('failed_count', 0)
        failed_numbers = ctx.get('failed_numbers', [])
        success_rate = (success_count / total_numbers * 100) if total_numbers > 0 else 0
        
        return jsonify({
            'success': True,
            'report': {
                'total_numbers': total_numbers,
                'success_count': success_count,
                'failed_count': failed_count,
                'success_rate': round(success_rate, 1),
                'failed_numbers': failed_numbers,
                'logs': ctx.get('logs', [])
            }
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Рассылка еще не завершена или не была запущена'
        })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)