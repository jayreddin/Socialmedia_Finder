// Global variables
let camera_active = false;
let analysisInterval = null;
let currentImageUrl = null;

document.addEventListener('DOMContentLoaded', function() {
    // Image Upload Section
    const imageUpload = document.getElementById('imageUpload');
    const uploadedFileName = document.getElementById('uploadedFileName');
    const analyzeButton = document.getElementById('analyzeButton');
    const uploadedImage = document.getElementById('uploadedImage');
    const uploadedImageCard = document.getElementById('uploadedImageCard');
    const analysisResultCard = document.getElementById('analysisResultCard');
    const uploadPersonInfo = document.getElementById('uploadPersonInfo');
    const uploadSceneInfo = document.getElementById('uploadSceneInfo');

    // Webcam Section
    const toggleCameraBtn = document.getElementById('toggleCamera');
    const takeSnapshotBtn = document.getElementById('takeSnapshot');
    const shareButton = document.getElementById('shareButton');
    const videoFeed = document.getElementById('videoFeed');
    const personInfo = document.getElementById('personInfo');
    const sceneInfo = document.getElementById('sceneInfo');

    // Image Upload Event Listeners
    imageUpload.addEventListener('change', function(event) {
        const file = event.target.files[0];
        if (file) {
            uploadedFileName.value = file.name;
            uploadedFileName.style.display = 'block';
            analyzeButton.style.display = 'block';

            const reader = new FileReader();
            reader.onload = function(e) {
                uploadedImage.src = e.target.result;
                uploadedImageCard.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });

    // Analyze Button Event Listener
    analyzeButton.addEventListener('click', function() {
        const file = imageUpload.files[0];
        if (file) {
            const formData = new FormData();
            formData.append('image', file);

            fetch('/analyze_upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Clear previous results
                uploadPersonInfo.innerHTML = '';
                uploadSceneInfo.innerHTML = '';

                // Person Details
                if (data.faces && data.faces.length > 0) {
                    const face = data.faces[0];
                    const details = face.details;
                    
                    uploadPersonInfo.innerHTML = `
                        <h6>Person Details</h6>
                        <p>Description: ${details.description}</p>
                        <p>Skin Tone: ${details.details.skin_tone}</p>
                        <p>Hair: ${details.details.hair.color} ${details.details.hair.style}</p>
                        <p>Eye Color: ${details.details.eyes.color}</p>
                        <p>Confidence: ${(details.details.confidence * 100).toFixed(0)}%</p>
                    `;
                } else {
                    uploadPersonInfo.innerHTML = '<p>No faces detected</p>';
                }

                // Scene Analysis
                if (data.background) {
                    uploadSceneInfo.innerHTML = `
                        <h6>Scene Analysis</h6>
                        <p>Description: ${data.background.description}</p>
                        <p>Lighting: ${data.background.lighting}</p>
                        <p>Scene Type: ${data.background.scene_type}</p>
                        <p>Timestamp: ${data.background.timestamp}</p>
                    `;
                } else {
                    uploadSceneInfo.innerHTML = '<p>Unable to analyze scene</p>';
                }

                // Show result cards
                uploadedImageCard.style.display = 'block';
                analysisResultCard.style.display = 'block';
            })
            .catch(error => {
                console.error('Error:', error);
                uploadPersonInfo.innerHTML = '<p>Error analyzing image</p>';
                analysisResultCard.style.display = 'block';
            });
        }
    });

    // Webcam Section
    let stream = null;
    let isWebcamOn = false;

    toggleCameraBtn.addEventListener('click', function() {
        if (!isWebcamOn) {
            // Start Camera
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(mediaStream => {
                    stream = mediaStream;
                    videoFeed.srcObject = stream;
                    videoFeed.style.display = 'block';
                    toggleCameraBtn.textContent = 'Stop Camera';
                    takeSnapshotBtn.disabled = false;
                    shareButton.disabled = false;
                    isWebcamOn = true;
                })
                .catch(err => {
                    console.error("Error accessing webcam:", err);
                });
        } else {
            // Stop Camera
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                videoFeed.style.display = 'none';
                toggleCameraBtn.textContent = 'Start Camera';
                takeSnapshotBtn.disabled = true;
                shareButton.disabled = true;
                isWebcamOn = false;
            }
        }
    });

    // Take Snapshot
    takeSnapshotBtn.addEventListener('click', function() {
        const canvas = document.createElement('canvas');
        canvas.width = videoFeed.videoWidth;
        canvas.height = videoFeed.videoHeight;
        canvas.getContext('2d').drawImage(videoFeed, 0, 0);
        
        // Convert canvas to blob
        canvas.toBlob(function(blob) {
            const formData = new FormData();
            formData.append('image', blob, 'snapshot.jpg');

            fetch('/analyze_webcam', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                // Clear previous results
                personInfo.innerHTML = '';
                sceneInfo.innerHTML = '';

                // Person Details
                if (data.faces && data.faces.length > 0) {
                    const face = data.faces[0];
                    const details = face.details;
                    
                    personInfo.innerHTML = `
                        <h6>Person Details</h6>
                        <p>Description: ${details.description}</p>
                        <p>Skin Tone: ${details.details.skin_tone}</p>
                        <p>Hair: ${details.details.hair.color} ${details.details.hair.style}</p>
                        <p>Eye Color: ${details.details.eyes.color}</p>
                        <p>Confidence: ${(details.details.confidence * 100).toFixed(0)}%</p>
                    `;
                } else {
                    personInfo.innerHTML = '<p>No faces detected</p>';
                }

                // Scene Analysis
                if (data.background) {
                    sceneInfo.innerHTML = `
                        <h6>Scene Analysis</h6>
                        <p>Description: ${data.background.description}</p>
                        <p>Lighting: ${data.background.lighting}</p>
                        <p>Scene Type: ${data.background.scene_type}</p>
                        <p>Timestamp: ${data.background.timestamp}</p>
                    `;
                } else {
                    sceneInfo.innerHTML = '<p>Unable to analyze scene</p>';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                personInfo.innerHTML = '<p>Error analyzing snapshot</p>';
            });
        }, 'image/jpeg');
    });

    // Share Button
    shareButton.addEventListener('click', function() {
        const canvas = document.createElement('canvas');
        canvas.width = videoFeed.videoWidth;
        canvas.height = videoFeed.videoHeight;
        canvas.getContext('2d').drawImage(videoFeed, 0, 0);
        
        const sharePreview = document.getElementById('sharePreview');
        sharePreview.src = canvas.toDataURL('image/jpeg');
        
        const shareModal = new bootstrap.Modal(document.getElementById('shareModal'));
        shareModal.show();
    });

    // Confirm Share
    document.getElementById('confirmShare').addEventListener('click', function() {
        const shareCaption = document.getElementById('shareCaption').value;
        // Implement actual sharing logic here (e.g., to social media platforms)
        console.log('Sharing with caption:', shareCaption);
        
        // Close modal
        const shareModal = bootstrap.Modal.getInstance(document.getElementById('shareModal'));
        shareModal.hide();
    });

    // Load existing snapshots when gallery tab is shown
    document.getElementById('gallery-tab').addEventListener('shown.bs.tab', loadGallery);
    
    // Share platform selection
    document.querySelectorAll('.dropdown-item[data-platform]').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const platform = e.target.dataset.platform;
            const caption = document.getElementById('shareCaption').value;
            const imageUrl = document.getElementById('sharePreview').src;
            
            shareToSocialMedia(platform, imageUrl, caption);
        });
    });

    async function loadGallery() {
        fetch('/get_snapshots')
            .then(response => response.json())
            .then(snapshots => {
                const gallery = document.getElementById('gallery');
                gallery.innerHTML = '';
                snapshots.forEach(snapshot => {
                    const col = document.createElement('div');
                    col.className = 'col-md-4 mb-3';
                    col.innerHTML = `
                        <div class="card">
                            <img src="${snapshot.url}" class="card-img-top" alt="Snapshot">
                            <div class="card-body">
                                <p class="card-text">Taken: ${snapshot.timestamp}</p>
                            </div>
                        </div>
                    `;
                    gallery.appendChild(col);
                });
            })
            .catch(error => {
                console.error('Error loading gallery:', error);
            });
    }

    async function shareToSocialMedia(platform, imageUrl, caption) {
        try {
            const response = await fetch('/share', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    platform,
                    image_url: imageUrl,
                    caption
                })
            });
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Close modal and show success message
            const shareModal = bootstrap.Modal.getInstance(document.getElementById('shareModal'));
            shareModal.hide();
            alert(data.message);
        } catch (error) {
            console.error('Error sharing to social media:', error);
            alert('Failed to share: ' + error.message);
        }
    }
});
