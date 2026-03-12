import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";

export class DashboardComponent extends Component {
    setup() {
        this.state = useState({ 
            status: "loading",
            error: null
        });
        
        this.REFRESH_INTERVAL = 5 * 60 * 1000;
        this._tempChart = null;
        this._windChart = null;
        this._refreshTimer = null;

        onMounted(() => {
            console.log("🟢 Dashboard component mounted");
            this.attachControls();
            this.updateAll();
            this._refreshTimer = setInterval(() => this.updateAll(), this.REFRESH_INTERVAL);
        });

        onWillUnmount(() => {
            this.cleanup();
        });
    }

    cleanup() {
        if (this._tempChart) this._tempChart.destroy();
        if (this._windChart) this._windChart.destroy();
        if (this._refreshTimer) clearInterval(this._refreshTimer);
    }

    n(v) { 
        return (v == null || isNaN(v)) ? null : Number(v); 
    }

    emojiForHour(t, r) {
        if (r === null || t === null) return "❓";
        if (r > 2) return "⛈️";
        if (r > 0) return "🌧️";
        if (t < 20) return "☁️";
        if (t > 33) return "🔥";
        return "🌤️";
    }

    async fetchWeather() {
        try {
            console.log("🟡 Fetching weather data...");
            
            const response = await fetch('/get/live-temperature', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({})
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            console.log("🟡 Raw response:", data);

            const result = data.result || data;
            
            if (result.error) throw new Error(result.error);
            if (result.success === false) throw new Error(result.error || "Request failed");

            let weatherData = result.data;
            if (result.raw_action && !weatherData) weatherData = result;

            if (!weatherData) throw new Error("No weather data found");

            console.log("🟡 Weather data structure:", weatherData);

            // FIX: The actual data is nested in weatherData.data.data_1h
            const actualData = weatherData.data || weatherData;
            const data_1h = actualData.data_1h;

            console.log("🟡 Actual data_1h:", data_1h);

            if (!data_1h) {
                throw new Error("No data_1h found in response");
            }

            // Extract arrays from the correct location
            const times = data_1h.time || [];
            const temps = (data_1h.temperature || []).map(v => this.n(v));
            const winds = (data_1h.windspeed || []).map(v => this.n(v));
            const rains = (data_1h.precipitation || []).map(v => this.n(v));

            console.log("✅ Extracted data:", {
                times: times.length,
                temps: temps.length,
                winds: winds.length,
                rains: rains.length
            });

            return { times, temps, winds, rains };

        } catch (error) {
            console.error("❌ fetchWeather error:", error);
            this.state.error = error.message;
            this.state.status = "error";
            return null;
        }
    }

    formatTimeLabel(ts) { 
        if (!ts) return '--';
        return ts.split(" ")[1]?.slice(0, 5) || ts.slice(11, 16); 
    }

    groupByDay(times, temps, winds, rains) {
        const out = {};
        times.forEach((t, i) => {
            if (!t) return;
            const day = t.split(" ")[0];
            if (!out[day]) out[day] = { temps: [], winds: [], rains: [], times: [] };
            out[day].temps.push(temps[i]);
            out[day].winds.push(winds[i]);
            out[day].rains.push(rains[i]);
            out[day].times.push(t);
        });
        return out;
    }

    fillHourlyTable(times, temps, winds, rains) {
        const hourlyDiv = document.querySelector(".hourly");
        if (!hourlyDiv) return;

        hourlyDiv.innerHTML = "";
        const today = new Date().toISOString().split("T")[0];

        times.forEach((t, i) => {
            if (!t.startsWith(today)) return;
            
            const card = document.createElement("div");
            card.className = "hour-card";
            card.innerHTML = `
                <div class="emoji">${this.emojiForHour(temps[i], rains[i])}</div>
                <div class="temp">${temps[i] !== null ? temps[i].toFixed(1) : '--'}°C</div>
                <div class="wind">${winds[i] !== null ? winds[i].toFixed(1) : '--'} km/h</div>
                <div class="rain">${rains[i] !== null ? rains[i].toFixed(1) : '--'} mm</div>
                <div class="time">${this.formatTimeLabel(t)}</div>
            `;
            hourlyDiv.appendChild(card);
        });
    }

    fillThreeDay(grouped) {
        const container = document.getElementById("threeDay");
        if (!container) return;

        container.innerHTML = "";
        Object.keys(grouped).slice(0, 3).forEach(day => {
            const d = grouped[day];
            const minT = Math.min(...d.temps);
            const maxT = Math.max(...d.temps);
            const avgW = d.winds.reduce((a, b) => a + b, 0) / d.winds.length;
            const sumR = d.rains.reduce((a, b) => a + b, 0);
            const icon = this.emojiForHour((minT + maxT) / 2, sumR);
            
            const el = document.createElement("div");
            el.className = "day-card";
            el.innerHTML = `
              <div class="day-left">
                <div class="emoji">${icon}</div>
                <div>
                  <div class="day-date">${day}</div>
                  <div class="day-weather">${minT.toFixed(1)}° / ${maxT.toFixed(1)}°</div>
                </div>
              </div>
              <div style="text-align:right">
                <div class="muted" style="font-size:0.85rem">Avg wind</div>
                <div style="font-weight:700">${avgW.toFixed(1)} km/h</div>
                <div class="muted" style="font-size:0.8rem;margin-top:6px">${sumR.toFixed(1)} mm total</div>
              </div>`;
            container.appendChild(el);
        });
    }

    renderCharts(times, temps, winds) {
        const today = new Date().toISOString().split("T")[0];
        const labels = [], tdata = [], wdata = [];
        
        times.forEach((t, i) => {
            if (!t.startsWith(today)) return;
            labels.push(this.formatTimeLabel(t));
            tdata.push(temps[i]);
            wdata.push(winds[i]);
        });

        try {
            const tctx = document.getElementById('tempChart');
            if (tctx && window.Chart) {
                if (this._tempChart) this._tempChart.destroy();
                this._tempChart = new Chart(tctx, {
                    type: 'line',
                    data: { 
                        labels, 
                        datasets: [{ 
                            label: 'Temperature (°C)', 
                            data: tdata, 
                            borderColor: '#f43f5e', 
                            backgroundColor: 'rgba(244, 63, 94, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true 
                        }] 
                    },
                    options: { 
                        responsive: true, 
                        plugins: { legend: { display: false } }
                    }
                });
            }

            const wctx = document.getElementById('windChart');
            if (wctx && window.Chart) {
                if (this._windChart) this._windChart.destroy();
                this._windChart = new Chart(wctx, {
                    type: 'bar',
                    data: { 
                        labels, 
                        datasets: [{ 
                            label: 'Wind Speed (km/h)', 
                            data: wdata,
                            backgroundColor: 'rgba(59, 130, 246, 0.8)',
                            borderColor: 'rgba(59, 130, 246, 1)',
                            borderWidth: 1
                        }] 
                    },
                    options: { 
                        responsive: true, 
                        plugins: { legend: { display: false } }
                    }
                });
            }
        } catch (e) {
            console.error("Chart error:", e);
        }
    }

    setLastUpdatedLabel() {
        const el = document.getElementById("lastUpdated");
        if (el) el.textContent = `Last updated: ${new Date().toLocaleString()}`;
    }

    updateCurrentTemperature(times, temps) {
        const tempEl = document.getElementById("currentTemp");
        const locationEl = document.getElementById("locationName");
        
        if (locationEl) locationEl.textContent = "Dhaka, Bangladesh";
        if (!tempEl || !times || times.length === 0) {
            if (tempEl) tempEl.textContent = "--°C";
            return;
        }

        const currentTemp = temps[0] !== null ? Math.round(temps[0]) : null;
        if (tempEl) tempEl.textContent = currentTemp !== null ? `${currentTemp}°C` : "--°C";
    }

    async updateAll() {
        try {
            this.state.status = "loading";
            this.state.error = null;
            
            console.log("🟡 Starting dashboard update...");
            const data = await this.fetchWeather();
            
            if (!data) throw new Error("No data received");

            const { times, temps, winds, rains } = data;
            
            if (!times || times.length === 0) {
                throw new Error("No time data available");
            }

            this.state.status = "ready";

            this.updateCurrentTemperature(times, temps);
            
            const grouped = this.groupByDay(times, temps, winds, rains);
            this.fillThreeDay(grouped);
            this.fillHourlyTable(times, temps, winds, rains);
            this.renderCharts(times, temps, winds);
            this.setLastUpdatedLabel();

            console.log("✅ Dashboard updated successfully");

        } catch (error) {
            console.error("❌ updateAll error:", error);
            this.state.status = "error";
            this.state.error = error.message;
        }
    }

    attachControls() {
        const refreshBtn = document.getElementById("refreshBtn");
        if (refreshBtn) {
            refreshBtn.addEventListener("click", async () => {
                const btn = refreshBtn;
                const originalText = btn.textContent;
                btn.textContent = "Refreshing...";
                btn.disabled = true;
                await this.updateAll();
                btn.textContent = originalText;
                btn.disabled = false;
            });
        }
    }

    willUnmount() {
        this.cleanup();
    }
}

DashboardComponent.template = "layer_temp_dash.DashboardTemplate";
registry.category("actions").add("layer_temp_dash.DashboardAction", DashboardComponent);
console.info("✅ Dashboard component registered");
