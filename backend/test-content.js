// Test script to validate content creation and posting
const fs = require('fs-extra');
const path = require('path');

// Create a test image for posting
async function createTestImage() {
    const sharp = require('sharp');
    
    // Create a simple test image
    const testImage = await sharp({
        create: {
            width: 400,
            height: 400,
            channels: 3,
            background: { r: 255, g: 100, b: 150 }
        }
    })
    .png()
    .toBuffer();
    
    const testImagePath = path.join(__dirname, 'temp', 'test-post.png');
    await fs.writeFile(testImagePath, testImage);
    
    console.log('✅ Test image created:', testImagePath);
    return testImagePath;
}

// Mock test content
const testContent = {
    id: 'test_' + Date.now(),
    type: 'post',
    url: 'https://example.com/test',
    imageUrl: 'https://picsum.photos/400/400?random=1',
    caption: '🚀 Testing Instagram Auto Poster! This is automated content. #test #automation',
    isVideo: false,
    timestamp: new Date().toISOString()
};

console.log('Test content created:', testContent);

module.exports = {
    createTestImage,
    testContent
};