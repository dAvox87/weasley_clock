class WeasleyClockAdvancedCard extends HTMLElement {
  setConfig(config) {
    this.config = config;
  }

  set hass(hass) {
    this.hass = hass;
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div style="padding: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
              <h2 style="margin: 0;">🧙 Weasley Clock</h2>
              <ha-button id="refresh-btn">🔄 Refresh</ha-button>
            </div>
            
            <div id="image-container" style="text-align: center; margin-bottom: 16px;">
              <img id="clock-image" 
                   src="" 
                   style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);"
                   alt="Weasley Clock">
            </div>

            <div style="background: var(--secondary-background-color); padding: 12px; border-radius: 8px; margin-bottom: 16px;">
              <div style="font-size: 0.9em;">
                <div style="margin-bottom: 8px;">
                  ⏱️ <strong>Last Updated:</strong> <span id="last-changed">-</span>
                </div>
                <div style="margin-bottom: 8px;">
                  📝 <strong>Reason:</strong> <span id="last-reason">-</span>
                </div>
                <div>
                  🔗 <strong>Path:</strong> <span id="image-path" style="word-break: break-all; font-size: 0.85em;">-</span>
                </div>
              </div>
            </div>

            <div id="users-section" style="margin-bottom: 16px;">
              <h3 style="margin: 0 0 12px 0; font-size: 1.1em;">👥 User Positions</h3>
              <div id="users-list" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px;">
                <!-- Users will be added here -->
              </div>
            </div>

            <div id="zones-section">
              <h3 style="margin: 0 0 12px 0; font-size: 1.1em;">📍 Zones</h3>
              <div id="zones-list" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px;">
                <!-- Zones will be added here -->
              </div>
            </div>
          </div>
        </ha-card>
      `;
      this.content = this.querySelector('[style*="padding"]');
      this.imageElement = this.querySelector('#clock-image');
      this.refreshBtn = this.querySelector('#refresh-btn');
      this.lastChangedElement = this.querySelector('#last-changed');
      this.lastReasonElement = this.querySelector('#last-reason');
      this.imagePathElement = this.querySelector('#image-path');
      this.usersListElement = this.querySelector('#users-list');
      this.zonesListElement = this.querySelector('#zones-list');
      
      this.refreshBtn.addEventListener('click', () => this.refreshImage());
    }

    this.updateCard();
  }

  updateCard() {
    // Update image
    const imagePath = this.config.image_path || '/local/weasley_clock.png';
    const timestamp = new Date().getTime();
    this.imageElement.src = `${imagePath}?t=${timestamp}`;

    // Update info
    const lastChanged = this.hass.states['sensor.weasley_clock_last_changed'];
    const imagePath_sensor = this.hass.states['sensor.weasley_clock_image_path'];
    
    if (lastChanged) {
      const changeTime = new Date(lastChanged.state).toLocaleTimeString();
      this.lastChangedElement.textContent = changeTime;
      this.lastReasonElement.textContent = lastChanged.attributes.reason || '-';
    }

    if (imagePath_sensor) {
      this.imagePathElement.textContent = imagePath_sensor.state || '-';
    }

    // Update users and zones
    this.updateUsersAndZones();
  }

  updateUsersAndZones() {
    // Get all person entities and their zones
    const personEntities = {};
    const zones = new Set();

    for (const [entityId, state] of Object.entries(this.hass.states)) {
      if (entityId.startsWith('person.')) {
        const attributes = state.attributes || {};
        const tags = attributes.tags || [];
        
        // Check if has weasleyclock tag
        if (tags.includes('weasleyclock')) {
          personEntities[entityId] = {
            name: attributes.friendly_name || entityId.split('.')[1],
            zone: state.state,
            picture: attributes.entity_picture || ''
          };
          zones.add(state.state);
        }
      }
    }

    // Update users list
    this.usersListElement.innerHTML = '';
    for (const [entityId, userData] of Object.entries(personEntities)) {
      const userDiv = document.createElement('div');
      userDiv.style.cssText = `
        background: var(--primary-color);
        color: white;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        font-size: 0.9em;
      `;
      
      const picture = userData.picture ? `<img src="${userData.picture}" style="width: 40px; height: 40px; border-radius: 50%; margin-bottom: 8px;">` : '👤';
      
      userDiv.innerHTML = `
        <div>${picture}</div>
        <div><strong>${userData.name}</strong></div>
        <div style="font-size: 0.85em; opacity: 0.9;">📍 ${userData.zone}</div>
      `;
      
      this.usersListElement.appendChild(userDiv);
    }

    if (Object.keys(personEntities).length === 0) {
      this.usersListElement.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--secondary-text-color);">No tagged users</div>';
    }

    // Update zones list
    this.zonesListElement.innerHTML = '';
    for (const zone of Array.from(zones).sort()) {
      const usersInZone = Object.entries(personEntities)
        .filter(([_, u]) => u.zone === zone)
        .map(([_, u]) => u.name);

      const zoneDiv = document.createElement('div');
      zoneDiv.style.cssText = `
        background: var(--secondary-background-color);
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        font-size: 0.9em;
        border-left: 4px solid var(--primary-color);
      `;
      
      zoneDiv.innerHTML = `
        <div><strong>${zone}</strong></div>
        <div style="font-size: 0.85em; color: var(--secondary-text-color);">
          ${usersInZone.length > 0 ? usersInZone.join(', ') : 'Empty'}
        </div>
      `;
      
      this.zonesListElement.appendChild(zoneDiv);
    }

    if (zones.size === 0) {
      this.zonesListElement.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--secondary-text-color);">No zones configured</div>';
    }
  }

  refreshImage() {
    if (this.hass.services.weasley_clock && this.hass.services.weasley_clock.generate_image) {
      this.hass.callService('weasley_clock', 'generate_image', {
        reason: 'Manual refresh via advanced card'
      });
      this.refreshBtn.textContent = '⏳ Updating...';
      setTimeout(() => {
        this.refreshBtn.textContent = '🔄 Refresh';
        this.updateCard();
      }, 1500);
    }
  }

  getCardSize() {
    return 8;
  }
}

customElements.define('weasley-clock-advanced', WeasleyClockAdvancedCard);
