// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  ADD MESSAGE - WITH CLICKABLE REFERENCES
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function addMessage(text, isUser, refs = [], isError = false) {
    hideWelcome();
    const msgs = $('messages');

    const cleanedText = cleanContent(text);

    const row = document.createElement('div');
    row.className = `msg-row ${isUser ? 'user' : 'ai'}`;

    const av = document.createElement('div');
    av.className = `avatar ${isUser ? 'user-av' : 'ai-av'}`;
    av.textContent = isUser ? 'U' : 'S';

    const bub = document.createElement('div');
    bub.className = 'bubble';
    
    if (isError) {
        bub.style.background = '#fef2f2';
        bub.style.border = '1px solid #fca5a5';
        bub.style.color = '#dc2626';
    }
    
    bub.innerHTML = cleanedText
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');

    // --- ADD CLICKABLE REFERENCES ---
    if (!isUser && refs && refs.length > 0) {
        const refsDiv = document.createElement('div');
        refsDiv.className = 'references-container';
        refsDiv.style.marginTop = '12px';
        refsDiv.style.paddingTop = '10px';
        refsDiv.style.borderTop = '1px solid rgba(255,255,255,0.08)';
        
        const label = document.createElement('span');
        label.className = 'refs-label';
        label.textContent = '📚 Sources: ';
        label.style.fontSize = '12px';
        label.style.color = '#888';
        label.style.fontWeight = '500';
        refsDiv.appendChild(label);
        
        refs.forEach((ref) => {
            const tag = document.createElement('a');
            tag.className = 'source-tag';
            tag.style.display = 'inline-block';
            tag.style.margin = '4px 6px 4px 0';
            tag.style.padding = '4px 12px';
            tag.style.borderRadius = '16px';
            tag.style.fontSize = '12px';
            tag.style.textDecoration = 'none';
            tag.style.background = 'rgba(59, 130, 246, 0.12)';
            tag.style.color = '#60a5fa';
            tag.style.border = '1px solid rgba(59, 130, 246, 0.15)';
            tag.style.cursor = 'pointer';
            tag.style.transition = 'all 0.2s ease';
            tag.style.fontWeight = '500';
            
            // --- HANDLE DIFFERENT SOURCE TYPES ---
            let icon = '📄';
            let linkText = ref.lesson;
            
            if (ref.source === 'pdf') {
                icon = '📄';
                if (ref.url) {
                    tag.href = ref.url;
                    tag.target = '_blank';
                    tag.title = 'Click to download PDF';
                    tag.download = ref.file_name || 'document.pdf';  // Force download
                }
            } else if (ref.source === 'video') {
                icon = '🎥';
                if (ref.url) {
                    tag.href = ref.url;
                    tag.target = '_blank';
                    tag.title = 'Click to watch video';
                }
            } else if (ref.source === 'text') {
                icon = '📝';
                if (ref.url) {
                    tag.href = ref.url;
                    tag.target = '_blank';
                    tag.title = 'Click to view text lesson';
                } else {
                    tag.style.cursor = 'default';
                    tag.style.opacity = '0.7';
                }
            }
            
            // Section info
            let sectionText = '';
            if (ref.section && ref.section !== 'General') {
                sectionText = ` (${ref.section})`;
            }
            
            // Display file name for PDFs if available
            let displayName = linkText;
            if (ref.source === 'pdf' && ref.file_name) {
                displayName = ref.file_name.replace(/\.[^/.]+$/, ''); // Remove extension
            }
            
            tag.innerHTML = `${icon} ${displayName}${sectionText}`;
            
            // Hover effect
            tag.onmouseover = function() {
                this.style.background = 'rgba(59, 130, 246, 0.25)';
                this.style.transform = 'scale(1.02)';
            };
            tag.onmouseout = function() {
                this.style.background = 'rgba(59, 130, 246, 0.12)';
                this.style.transform = 'scale(1)';
            };
            
            // For PDFs, add download icon
            if (ref.source === 'pdf' && ref.url) {
                const downloadIcon = document.createElement('span');
                downloadIcon.textContent = ' ⬇️';
                downloadIcon.style.fontSize = '10px';
                tag.appendChild(downloadIcon);
            }
            
            // For videos, add play icon
            if (ref.source === 'video' && ref.url) {
                const playIcon = document.createElement('span');
                playIcon.textContent = ' ▶️';
                playIcon.style.fontSize = '10px';
                tag.appendChild(playIcon);
            }
            
            refsDiv.appendChild(tag);
        });
        
        bub.appendChild(refsDiv);
    }

    row.appendChild(av);
    row.appendChild(bub);
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
}