class WeasleyClockSimpleCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
  }

  set hass(hass) {
    this.hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="card-content">
            <div id="image-container" style="text-align: center;">
              <img id="clock-image" 
                   src="" 
                   style="max-width: 100%; height: auto; border-radius: 8px;"
                   alt="Weasley Clock">
            </div>
            <div style="text-align: center; margin-top: 16px;">
              <ha-button id="refresh-btn">🔄 Refresh</ha-button>
            </div>
            <div id="info" style="text-align: center; margin-top: 12px; font-size: 0.9em; color: var(--secondary-text-color);"></div>
          </div>
        </ha-card>
      `;
      this.content = this.querySelector('.card-content');
      this.imageElement = this.querySelector('#clock-image');
      this.refreshBtn = this.querySelector('#refresh-btn');
      this.infoElement = this.querySelector('#info');
      
      this.refreshBtn.addEventListener('click', () => this.refreshImage());
    }

    this.updateImage();
  }

  updateImage() {
    const imagePath = this.config.image_path || '/local/weasley_clock.png';
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    this.imageElement.src = `${imagePath}?t=${timestamp}`;
    
    const lastChanged = this.hass.states['sensor.weasley_clock_last_changed'];
    if (lastChanged) {
      const changeTime = new Date(lastChanged.state).toLocaleTimeString();
      this.infoElement.innerHTML = `⏱️ Aggiornato: ${changeTime}`;
    }
  }

  refreshImage() {
    if (this.hass.services.weasley_clock && this.hass.services.weasley_clock.generate_image) {
      this.hass.callService('weasley_clock', 'generate_image', {
        reason: 'Manual refresh via card'
      });
      this.refreshBtn.textContent = '⏳ Aggiornamento...';
      setTimeout(() => {
        this.refreshBtn.textContent = '🔄 Refresh';
        this.updateImage();
      }, 1000);
    }
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('weasley-clock-simple', WeasleyClockSimpleCard);
