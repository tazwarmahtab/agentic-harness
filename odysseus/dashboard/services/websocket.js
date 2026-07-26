/**
 * AOS Dashboard WebSocket Client.
 * Connects through Odysseus proxy (never direct to port 7001).
 * Provides live execution streaming with auto-reconnect.
 */

class AosWebSocket {
  constructor() {
    this._ws = null;
    this._listeners = new Map();
    this._reconnectTimer = null;
    this._reconnectDelay = 1000;
    this._maxReconnectDelay = 30000;
    this._harnessName = null;

    // Message queue for offline support
    this._messageQueue = [];
    this._connectionState = 'disconnected'; // 'disconnected' | 'connecting' | 'connected' | 'reconnecting'
  }

  connect(harnessName, opts = {}) {
    this.disconnect();
    this._harnessName = harnessName;
    this._setConnectionState('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let url = `${protocol}//${window.location.host}/ws/harness/${encodeURIComponent(harnessName)}`;
    if (opts.token) url += `?token=${encodeURIComponent(opts.token)}`;

    this._ws = new WebSocket(url);
    this._ws.binaryType = 'arraybuffer';

    this._ws.onopen = () => {
      this._reconnectDelay = 1000;
      this._setConnectionState('connected');
      this._flushQueue();
      this._emit('connected', { harness: harnessName });
    };

    this._ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        this._emit(data.event || 'message', data);
      } catch {
        this._emit('message', { raw: evt.data });
      }
    };

    this._ws.onerror = (err) => {
      this._emit('error', { message: 'WebSocket error', error: err });
    };

    this._ws.onclose = (evt) => {
      this._setConnectionState('disconnected');
      this._emit('disconnected', { code: evt.code, reason: evt.reason });
      if (evt.code !== 1000 && this._harnessName) {
        this._setConnectionState('reconnecting');
        this._scheduleReconnect();
      }
    };
  }

  disconnect() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    this._harnessName = null;
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.close(1000);
      this._ws = null;
    }
    this._setConnectionState('disconnected');
  }

  on(event, callback) {
    if (!this._listeners.has(event)) this._listeners.set(event, new Set());
    this._listeners.get(event).add(callback);
    return () => this._listeners.get(event)?.delete(callback);
  }

  _emit(event, data) {
    this._listeners.get(event)?.forEach((cb) => {
      try { cb(data); } catch (e) { console.error('WS listener error:', e); }
    });
  }

  _setConnectionState(state) {
    if (this._connectionState !== state) {
      this._connectionState = state;
      this._emit('connectionStateChange', { state, timestamp: Date.now() });
    }
  }

  get connectionState() {
    return this._connectionState;
  }

  onConnectionStateChange(callback) {
    return this.on('connectionStateChange', callback);
  }

  send(data) {
    const message = typeof data === 'string' ? data : JSON.stringify(data);
    if (this.isConnected) {
      this._ws.send(message);
      return true;
    } else {
      this._messageQueue.push(message);
      return false;
    }
  }

  _flushQueue() {
    while (this._messageQueue.length > 0 && this.isConnected) {
      const message = this._messageQueue.shift();
      try { this._ws.send(message); } catch (e) { console.error('Flush queue error:', e); }
    }
  }

  _scheduleReconnect() {
    if (this._reconnectTimer) return;
    this._reconnectTimer = setTimeout(() => {
      this._reconnectTimer = null;
      if (this._harnessName) {
        this.connect(this._harnessName);
        this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
      }
    }, this._reconnectDelay);
  }

  get isConnected() {
    return this._ws?.readyState === WebSocket.OPEN;
  }
}

export const ws = new AosWebSocket();
export default ws;
