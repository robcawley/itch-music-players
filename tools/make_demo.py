"""Makes two short synthetic demo pieces (no samples, no recordings) so the players have something to play."""
import numpy as np, wave, sys, os
SR=44100
def write(path,x):
    x=np.clip(x,-1,1); s=(x*32767).astype('<i2')
    st=np.stack([s,np.roll(s,int(0.012*SR))],1)   # slight stereo offset
    with wave.open(path,'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
rng=np.random.default_rng(7)
def drone(sec):
    t=np.arange(int(sec*SR))/SR; x=np.zeros_like(t)
    for f,a in [(55,.5),(82.4,.3),(110.5,.25),(164.9,.12),(220,.08)]:
        lfo=1+.3*np.sin(2*np.pi*(0.05+f/2000)*t+f)
        x+=a*lfo*np.sin(2*np.pi*f*t+np.sin(2*np.pi*.07*t)*.8)
    n=rng.normal(0,1,len(t)); k=np.ones(400)/400; n=np.convolve(n,k,'same')*3
    swell=.55+.45*np.sin(2*np.pi*t/23)**2
    return (x*.35+n*.05)*swell
def pulse(sec,bpm):
    n=int(sec*SR); t=np.arange(n)/SR; x=drone(sec)*.4
    beat=60/bpm; env=np.interp(t,[0,sec*.25,sec*.55,sec*.8,sec],[.25,.45,1,.7,.2])
    for k in np.arange(0,sec-.5,beat):
        i=int(k*SR); m=min(int(.35*SR),n-i); tt=np.arange(m)/SR
        kick=np.sin(2*np.pi*(48+110*np.exp(-tt*30))*tt)*np.exp(-tt*9)
        x[i:i+m]+=kick*.8*env[i]
        if int(round(k/beat))%2==1:
            sn=rng.normal(0,1,m)*np.exp(-tt*25)*.25; x[i:i+m]+=sn*env[i]
    for k in np.arange(beat/2,sec-.2,beat):
        i=int(k*SR); m=min(int(.05*SR),n-i); x[i:i+m]+=rng.normal(0,1,m)*np.exp(-np.arange(m)/SR*90)*.08*env[i]
    return x*.9
out=sys.argv[1]; os.makedirs(out,exist_ok=True)
write(out+"/01 Demo Drone.wav",drone(70)/1.0)
write(out+"/02 Demo Pulse 95 BPM.wav",pulse(64,95))
print("ok")
