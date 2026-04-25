class WeasleyClockSimpleCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
  }

  set hass(hass) {
    this.hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div style="padding: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h2 style="margin: 0;">🧙 Weasley Clock</h2>
              <ha-button id="refresh-btn">🔄</ha-button>
            </div>
            
            <div id="image-container" style="text-align: center;">
              <img id="clock-image" 
                   src="" 
                   style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);"
                   alt="Weasley Clock">
            </div>

            <div style="text-align: center; margin-top: 12px; font-size: 0.85em; color: var(--secondary-text-color);">
              <span id="last-updated">Last updated: -</span>
            </div>
          </div>
        </ha-card>
      `;
      this.content = this.querySelector('[style*="padding"]');
      this.imageElement = this.querySelector('#clock-image');
      this.refreshBtn = this.querySelector('#refresh-btn');
      this.lastUpdatedElement = this.querySelector('#last-updated');
      
      this.refreshBtn.addEventListener('click', () => this.refreshImage());
    }

    this.updateCard();
  }

  updateCard() {
    // Update image with timestamp to prevent caching
    const imagePath = this.config.image_path || '/local/weasley_clock.png';
    const timestamp = new Date().getTime();
    this.imageElement.src = `${imagePath}?t=${timestamp}`;

    // Update last updated time
    const lastChanged = this.hass.states['sensor.weasley_clock_last_changed'];
    if (lastChanged) {
      const changeTime = new Date(lastChanged.state).toLocaleTimeString();
      this.lastUpdatedElement.textContent = `Last updated: ${changeTime}`;
    }
  }

  refreshImage() {
    if (this.hass.services.weasley_clock && this.hass.services.weasley_clock.generate_image) {
      this.hass.callService('weasley_clock', 'generate_image', {
        reason: 'Manual refresh via simple card'
      });
      this.refreshBtn.textContent = '⏳';
      setTimeout(() => {
        this.refreshBtn.textContent = '🔄';
        this.updateCard();
      }, 1500);
    }
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('weasley-clock-simple', WeasleyClockSimpleCard);
