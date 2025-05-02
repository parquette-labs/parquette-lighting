from typing import Optional
from .generator import Generator


class ImpulseGenerator(Generator):

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        amp: float = 0.5,
        offset: float = 0.5,
        period: int = 1000,
        echo: int = 1,
        echo_decay: float = 1,
        duty: int = 100
    ):
        super().__init__(name=name, amp=amp, offset=offset, period=period, phase=0)

        self._echo = echo
        self._echo_decay = echo_decay
        self.duty = duty

    @property
    def echo(self) -> int:
        return self._echo

    @echo.setter
    def echo(self, value: int) -> None:
        self._echo = max(value, 1)

    def punch(self, millis: int) -> None:
        self.punch_point_millis = millis

    def value(self, millis) -> float:
        return 0


# import processing.core.PApplet;

# public class ImpulseGenerator extends Generator {

#     int punchPointMillis;
#     int duty;
#     int echo;
#     float echoDecay;

#     public ImpulseGenerator(PApplet p, String name, float amp, int period, int duty, int echo, float echoDecay) {
#         super(p, name, amp, 0, period);
#         this.duty = duty;
#         this.echo = echo;
#         this.echoDecay = echoDecay;
#     }

#     public void punch(int millis) {
#         punchPointMillis = millis;
#     }

#     public void setEcho(int echo) {
#         this.echo = echo;
#     }

#     public void setDecay(float echoDecay) {
#         this.echoDecay = echoDecay;
#     }

#     public void setDuty(int duty) {
#         this.duty = duty;
#     }

#     public float value(int millis) {
#         int ellapse = millis - punchPointMillis;
#         int count = ellapse / period;
#         if (count >= echo) return 0.0f;

#         if (ellapse % period > 0 && ellapse % period < duty) {
#             return amp * p.pow(echoDecay, count);
#         } else {
#             return 0.0f;
#         }
#     }

# }
