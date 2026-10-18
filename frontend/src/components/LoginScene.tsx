import { useRef, type PointerEvent } from 'react';
import Icon from './Icon';

/** Decorative CSS 3D scene. No personal data or request statuses are simulated. */
export default function LoginScene() {
  const frame = useRef<HTMLDivElement>(null);
  function move(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== 'mouse' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const box = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - box.left) / box.width - 0.5) * 10;
    const y = ((event.clientY - box.top) / box.height - 0.5) * -8;
    frame.current?.style.setProperty('--scene-rx', `${y.toFixed(2)}deg`);
    frame.current?.style.setProperty('--scene-ry', `${x.toFixed(2)}deg`);
  }
  function reset() {
    frame.current?.style.setProperty('--scene-rx', '0deg');
    frame.current?.style.setProperty('--scene-ry', '0deg');
  }
  return <div className="login-scene" onPointerMove={move} onPointerLeave={reset} aria-hidden="true">
    <div className="scene-glow" />
    <div className="scene-parallax" ref={frame}>
      <div className="scene-orbit scene-orbit-one" />
      <div className="scene-orbit scene-orbit-two" />
      <div className="scene-platform-wrap">
        <div className="scene-platform">
          <div className="scene-slab scene-slab-bottom" />
          <div className="scene-slab scene-slab-middle" />
          <div className="scene-slab scene-slab-top"><span>Q<span>11</span></span></div>
        </div>
      </div>
      <div className="scene-float scene-float-profile">
        <div className="scene-mini-card scene-profile-card"><span className="scene-avatar"><Icon name="person" size={24} /></span><span><strong>Ваш профиль</strong><small>Всё важное под рукой</small></span><span className="scene-mini-dot" /></div>
      </div>
      <div className="scene-float scene-float-request">
        <div className="scene-mini-card scene-request-card"><span className="scene-feature-icon"><Icon name="doc" size={24} /></span><span><strong>Мои заявки</strong><small>Каждый шаг — в кабинете</small></span><span className="scene-check"><Icon name="check" size={18} /></span></div>
      </div>
      <div className="scene-float scene-float-course">
        <div className="scene-mini-card scene-course-card"><span className="scene-feature-icon"><Icon name="book" size={22} /></span><span><strong>Jana Academy</strong><small>Новый шаг в развитии</small></span><span className="scene-course-lines"><i /><i /><i /></span></div>
      </div>
      <span className="scene-particle scene-particle-one" /><span className="scene-particle scene-particle-two" /><span className="scene-particle scene-particle-three" />
    </div>
  </div>;
}
