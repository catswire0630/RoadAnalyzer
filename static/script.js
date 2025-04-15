document.addEventListener('DOMContentLoaded', () => {
    // 检查登录状态
    if (!localStorage.getItem('isLoggedIn')) {
        window.location.href = '/static/login.html';
        return;
    }

    const role = localStorage.getItem('role');
    const adminOnlyElements = document.querySelectorAll('.admin-only');

    // 角色控制
    if (role === 'admin') {
        adminOnlyElements.forEach(el => el.style.display = 'block');
    } else {
        adminOnlyElements.forEach(el => el.style.display = 'none');
    }

    // 导航切换
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.section');

    function showSection(sectionId) {
        sections.forEach(section => section.style.display = 'none');
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.style.display = 'block';
        }
        navLinks.forEach(link => link.classList.remove('active'));
        const activeLink = document.querySelector(`.nav-link[data-section="${sectionId}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
    }
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = link.getAttribute('data-section');
            if (sectionId) {
                sections.forEach(section => section.style.display = 'none');
                document.getElementById(sectionId).style.display = 'block';
                navLinks.forEach(l => l.classList.remove('active'));
                link.classList.add('active');
            }
        });
    });



    // 页面加载时默认显示上传与检测
    showSection('upload-section');




    // 移动端导航切换
    const navbarToggler = document.querySelector('.navbar-toggler');
    const sidebar = document.querySelector('.sidebar');
    if (navbarToggler && sidebar) {
        navbarToggler.addEventListener('click', () => {
            sidebar.classList.toggle('active');
        });
    }

    // 登出
    document.getElementById('logoutBtn').addEventListener('click', () => {
        localStorage.removeItem('isLoggedIn');
        localStorage.removeItem('role');
        window.location.href = '/static/login.html';
    });

    // 主题切换
    const themeToggle = document.getElementById('themeToggle');
    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark');
        const icon = themeToggle.querySelector('i');
        if (document.body.classList.contains('dark')) {
            icon.classList.replace('fa-moon', 'fa-sun');
        } else {
            icon.classList.replace('fa-sun', 'fa-moon');
        }
    });

    // 进度条模拟
    function simulateProgress(progressBar, callback) {
        let width = 0;
        const interval = setInterval(() => {
            width += 10;
            progressBar.style.width = `${width}%`;
            if (width >= 100) {
                clearInterval(interval);
                callback();
            }
        }, 100);
    }

    // 防抖
    function debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // 更新数据看板（管理员）
    async function updateDashboard() {
        if (role !== 'admin') return;
        try {
            const response = await axios.get('/dashboard');
            document.getElementById('totalDetections').textContent = response.data.total_detections;
            document.getElementById('dailyDetections').textContent = response.data.daily_detections;
            document.getElementById('totalWarnings').textContent = response.data.total_warnings;
            document.getElementById('dailyWarnings').textContent = response.data.daily_warnings;
            document.getElementById('totalQA').textContent = response.data.total_qa;
        } catch (error) {
            console.error('获取数据看板失败:', error);
        }
    }

    // 更新历史记录（管理员）
    async function updateHistory() {
        if (role !== 'admin') return;
        try {
            const response = await axios.get('/history');
            const historyTableBody = document.getElementById('historyTableBody');
            historyTableBody.innerHTML = '';
            response.data.forEach(record => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${record.id}</td>
                    <td>${record.filename}</td>
                    <td>${new Date(record.timestamp).toLocaleString()}</td>
                    <td>${record.type === 'image' ? '图片' : '视频'}</td>
                `;
                historyTableBody.appendChild(row);
            });
        } catch (error) {
            console.error('获取历史记录失败:', error);
        }
    }

    // 更新预警记录
    async function updateWarnings() {
        try {
            const response = await axios.get('/warnings');
            const warningsTableBody = document.getElementById('warningsTableBody');
            warningsTableBody.innerHTML = '';
            response.data.forEach(warning => {
                const row = document.createElement('tr');
                let warningText = warning.warning_type;
                if (warning.warning_type === 'car_overspeed') {
                    warningText = '车辆超速';
                } else if (warning.warning_type === 'person_in_danger') {
                    warningText = '行人进入危险区域';
                } else if (warning.warning_type === 'car_in_danger') {
                    warningText = '车辆进入危险区域';
                } else if (warning.warning_type === 'crowd') {
                    warningText = '拥堵';
                } else if (warning.warning_type === 'person_stop') {
                    warningText = '行人停留';
                }
                row.innerHTML = `
                    <td>${warning.id}</td>
                    <td>${warning.track_id || '-'}</td>
                    <td>${warningText}</td>
                    <td><img src="/static/${warning.image_path}" style="width: 100px; height: auto;"></td>
                    <td>${new Date(warning.timestamp).toLocaleString()}</td>
                `;
                warningsTableBody.appendChild(row);
            });
        } catch (error) {
            console.error('获取预警记录失败:', error);
        }
    }

    // 初始化
    if (role === 'admin') {
        updateDashboard();
        updateHistory();
    }
    updateWarnings();

    // 上传逻辑
    document.getElementById('uploadBtn').addEventListener('click', async function () {
        const fileInput = document.getElementById('uploadInput');
        const file = fileInput.files[0];
        if (!file) {
            alert('请先选择一个文件！');
            return;
        }
        const isVideo = file.type.startsWith('video/');
        const formData = new FormData();
        formData.append("file", file);
        const progress = document.getElementById('uploadProgress');
        const progressBar = document.getElementById('uploadProgressBar');
        progress.style.display = 'block';
        this.disabled = true;
        try {
            await new Promise(resolve => {
                simulateProgress(progressBar, async () => {
                    const response = await axios.post('/upload', formData, {
                        headers: { 'Content-Type': 'multipart/form-data' }
                    });
                    const filePath = `/${response.data.file_path}`;
                    if (isVideo) {
                        const uploadedVideo = document.getElementById('uploadedVideo');
                        uploadedVideo.src = filePath;
                        uploadedVideo.style.display = 'block';
                        uploadedVideo.load();
                        uploadedVideo.play().catch(e => console.error('播放失败:', e));
                        document.getElementById('uploadedImage').style.display = 'none';
                        document.getElementById('rightPanelTitle').textContent = '标注视频';
                        document.getElementById('heatmapImage').style.display = 'none';
                        document.getElementById('annotatedVideo').style.display = 'none';
                    } else {
                        const uploadedImage = document.getElementById('uploadedImage');
                        uploadedImage.src = filePath;
                        uploadedImage.style.display = 'block';
                        document.getElementById('uploadedVideo').style.display = 'none';
                        document.getElementById('rightPanelTitle').textContent = '热力图';
                        document.getElementById('heatmapImage').style.display = 'none';
                        document.getElementById('annotatedVideo').style.display = 'none';
                    }
                    document.getElementById('detectBtn').dataset.filename = response.data.filename;
                    document.getElementById('detectBtn').dataset.isVideo = isVideo;
                    document.getElementById('detectBtn').disabled = false;
                    alert('文件上传成功！');
                    resolve();
                });
            });
        } catch (error) {
            console.error('文件上传失败:', error);
            alert('文件上传失败，请重试！');
        } finally {
            progress.style.display = 'none';
            progressBar.style.width = '0%';
            this.disabled = false;
        }
    });

    // 检测逻辑
    let warningMode = false;
    document.getElementById('warningModeBtn').addEventListener('click', function () {
        warningMode = !warningMode;
        this.textContent = warningMode ? '关闭预警模式' : '开启预警模式';
        this.classList.toggle('btn-warning');
        this.classList.toggle('btn-secondary');
        console.log('预警模式:', warningMode);
        alert(warningMode ? '预警模式已开启成功！' : '预警模式已关闭！');
    });

    const detectBtn = document.getElementById('detectBtn');
    detectBtn.addEventListener('click', debounce(async function () {
        const filename = this.dataset.filename;
        const isVideo = this.dataset.isVideo === 'true';
        if (!filename) {
            alert('请先上传文件！');
            return;
        }
        const loading = document.getElementById('loading');
        const progress = document.getElementById('detectProgress');
        const progressBar = document.getElementById('detectProgressBar');
        loading.style.display = 'inline-block';
        progress.style.display = 'block';
        this.disabled = true;

        try {
            await new Promise(resolve => {
                simulateProgress(progressBar, async () => {
                    console.log('开始检测请求:', filename, '预警模式:', warningMode);
                    const detectResponse = await axios.get(`/detect/${encodeURIComponent(filename)}`, {
                        params: { warning_mode: warningMode }
                    });
                    console.log('检测结果:', detectResponse.data);
                    if (detectResponse.data.error) {
                        alert(`检测失败: ${detectResponse.data.error}`);
                        resolve();
                        return;
                    }

                    if (isVideo) {
                        const annotatedVideoPath = `/static/${detectResponse.data.annotated_video_path.replace(/^static\//, '')}`;
                        const annotatedVideo = document.getElementById('annotatedVideo');
                        console.log('设置视频路径:', annotatedVideoPath);
                        annotatedVideo.src = annotatedVideoPath;
                        annotatedVideo.style.display = 'block';
                        annotatedVideo.load();
                        annotatedVideo.onerror = () => {
                            console.error('视频加载失败:', annotatedVideoPath);
                            alert('无法加载标注视频，请检查文件或网络！');
                        };
                        annotatedVideo.onloadeddata = () => {
                            console.log('视频加载成功，开始播放');
                            annotatedVideo.play().catch(e => console.error('播放失败:', e));
                        };
                        document.getElementById('heatmapImage').style.display = 'none';
                        document.getElementById('rightPanelTitle').textContent = '标注视频';
                        document.getElementById('detectionSummary').style.display = 'none';
                        document.getElementById('uploadedImage').style.display = 'none';

                        if (warningMode && detectResponse.data.warnings && detectResponse.data.warnings.length > 0) {
                            detectResponse.data.warnings.forEach(warning => {
                                let displayMessage = warning.message;
                                if (warning.type === 'car_overspeed') {
                                    displayMessage = `超速警告：${warning.message}`;
                                } else if (warning.type.includes('in_danger')) {
                                    displayMessage = `危险区域警告：${warning.message}`;
                                }
                                alert(displayMessage);
                                const utterance = new SpeechSynthesisUtterance(displayMessage);
                                utterance.lang = 'zh-CN';
                                window.speechSynthesis.speak(utterance);
                            });
                            await updateWarnings();
                        }
                    } else {
                        const annotatedImagePath = `/static/${detectResponse.data.annotated_image_path.
                        replace(/^static\//, '')}`;
                        const uploadedImage = document.getElementById('uploadedImage');
                        uploadedImage.src = annotatedImagePath;
                        uploadedImage.style.display = 'block';
                        if (detectResponse.data.heatmap_image_path) {
                            const heatmapImagePath = `/static/${detectResponse.data.heatmap_image_path.
                            replace(/^static\//,'')}`;
                            const heatmapImage = document.getElementById('heatmapImage');
                            heatmapImage.src = heatmapImagePath;
                            heatmapImage.style.display = 'block';
                        }
                        const classCounts = detectResponse.data.class_counts || {};
                        let summaryText = '';
                        if (Object.keys(classCounts).length > 0) {
                            summaryText = Object.entries(classCounts)
                                .map(([cls, count]) => `${cls === 'person' ? '人' : cls === 'car' ? '车' : cls}: ${count}`)
                                .join('，');
                        } else {
                            summaryText = '未检测到目标';
                        }
                        document.getElementById('summaryText').textContent = summaryText;
                        document.getElementById('detectionSummary').style.display = 'block';
                        document.getElementById('annotatedVideo').style.display = 'none';
                        document.getElementById('rightPanelTitle').textContent = '热力图';
                    }

                    if (role === 'admin') {
                        await Promise.all([updateDashboard(), updateHistory()]);
                    }
                    resolve();
                });
            });
        } catch (error) {
            console.error('检测失败:', error);
            alert('检测失败，请重试！');
        } finally {
            loading.style.display = 'none';
            progress.style.display = 'none';
            progressBar.style.width = '0%';
            this.disabled = false;
        }
    }, 300));

    // 实时监控
    document.getElementById('streamBtn').addEventListener('click', function () {
        const streamContainer = document.getElementById('streamContainer');
        const streamImage = document.getElementById('streamImage');
        const loading = document.getElementById('loading');

        if (streamContainer.style.display === 'none' || streamContainer.style.display === '') {
            streamImage.src = '/stream';
            streamContainer.style.display = 'block';
            loading.style.display = 'inline-block';
            this.textContent = '停止监控';
            this.classList.replace('btn-info', 'btn-warning');

            streamImage.onload = () => {
                console.log('实时监控流已加载');
                loading.style.display = 'none';
            };
            streamImage.onerror = () => {
                console.error('实时监控流加载失败');
                loading.style.display = 'none';
                alert('无法加载实时监控流，请检查后端服务！');
                streamContainer.style.display = 'none';
                this.textContent = '实时监控';
                this.classList.replace('btn-warning', 'btn-info');
            };
        } else {
            streamImage.src = '';
            streamContainer.style.display = 'none';
            loading.style.display = 'none';
            this.textContent = '实时监控';
            this.classList.replace('btn-warning', 'btn-info');
        }
    });

    // 交通问答
    document.getElementById('qaSubmitBtn').addEventListener('click', async function () {
        const qaInput = document.getElementById('qaInput').value.trim();
        const qaResult = document.getElementById('qaResult');
        const qaAnswerText = document.getElementById('qaAnswerText');

        if (!qaInput) {
            alert('请输入一个问题！');
            return;
        }

        this.disabled = true;
        qaAnswerText.textContent = '正在查询...';
        qaResult.style.display = 'block';
        qaResult.classList.remove('show');
        setTimeout(() => qaResult.classList.add('show'), 10);

        try {
            const response = await axios.post('/traffic-qa', {
                question: qaInput
            });
            qaAnswerText.textContent = response.data.answer;
            if (role === 'admin') {
                await updateDashboard();
            }
        } catch (error) {
            console.error('问答请求失败:', error);
            qaAnswerText.textContent = '抱歉，查询失败，请稍后重试。';
        } finally {
            this.disabled = false;
        }
    });

    // 语音输入
    document.getElementById('voiceInputBtn').addEventListener('click', function () {
        const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = 'zh-CN';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.start();
        this.disabled = true;
        this.classList.add('recording');

        recognition.onresult = (event) => {
            document.getElementById('qaInput').value = event.results[0][0].transcript;
            this.disabled = false;
            this.classList.remove('recording');
        };

        recognition.onerror = (event) => {
            console.error('语音识别错误:', event.error);
            alert('语音输入失败，请检查麦克风！');
            this.disabled = false;
            this.classList.remove('recording');
        };

        recognition.onend = () => {
            this.disabled = false;
            this.classList.remove('recording');
        };
    });

    // 语音输出
    document.getElementById('voiceOutputBtn').addEventListener('click', function () {
        const answerText = document.getElementById('qaAnswerText').textContent;
        if (!answerText || answerText === '正在查询...') {
            alert('暂无回答内容可播放！');
            return;
        }

        const utterance = new SpeechSynthesisUtterance(answerText);
        utterance.lang = 'zh-CN';
        utterance.rate = 1.0;
        window.speechSynthesis.speak(utterance);
    });

    // 清空预警（管理员）
    const clearWarningsBtn = document.getElementById('clearWarningsBtn');
    if (clearWarningsBtn) {
        clearWarningsBtn.addEventListener('click', async function () {
            if (confirm('确定要清空所有预警记录吗？')) {
                try {
                    const response = await axios.delete('/warnings');
                    if (response.data.success) {
                        alert('预警记录已清空！');
                        await updateWarnings();
                    } else {
                        alert('清空失败：' + response.data.error);
                    }
                } catch (error) {
                    console.error('清空预警记录失败:', error);
                    alert('清空预警记录失败，请重试！');
                }
            }
        });
    }
});