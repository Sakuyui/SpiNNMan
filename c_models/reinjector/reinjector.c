// SARK-based program
#include <sark.h>
#include <stdbool.h>

extern void spin1_wfi();
extern INT_HANDLER sark_int_han(void);

// ------------------------------------------------------------------------
// constants
// ------------------------------------------------------------------------

// The initial timeout of the router
#define ROUTER_INITIAL_TIMEOUT 0x004f0000

// Amount to call the timer callback
#define TICK_PERIOD        10

// dumped packet queue length
#define PKT_QUEUE_SIZE     256

// CPU VIC slot (watchdog and SDP)
#define CPU_SLOT           SLOT_0

// comms. cont. VIC slot
#define CC_SLOT            SLOT_1

// timer VIC slot
#define TIMER_SLOT         SLOT_2

#define RTR_BLOCKED_BIT    25
#define RTR_DOVRFLW_BIT    30
#define RTR_DENABLE_BIT    2

#define RTR_BLOCKED_MASK   (1 << RTR_BLOCKED_BIT)   // router blocked
#define RTR_DOVRFLW_MASK   (1 << RTR_DOVRFLW_BIT)   // router dump overflow
#define RTR_DENABLE_MASK   (1 << RTR_DENABLE_BIT)   // enable dump interrupts

#define PKT_CONTROL_SHFT   16
#define PKT_PLD_SHFT       17
#define PKT_TYPE_SHFT      22
#define PKT_ROUTE_SHFT     24

#define PKT_CONTROL_MASK   (0xff << PKT_CONTROL_SHFT)
#define PKT_PLD_MASK       (1 << PKT_PLD_SHFT)
#define PKT_TYPE_MASK      (3 << PKT_TYPE_SHFT)
#define PKT_ROUTE_MASK     (7 << PKT_ROUTE_SHFT)

#define PKT_TYPE_MC        (0 << PKT_TYPE_SHFT)
#define PKT_TYPE_PP        (1 << PKT_TYPE_SHFT)
#define PKT_TYPE_NN        (2 << PKT_TYPE_SHFT)
#define PKT_TYPE_FR        (3 << PKT_TYPE_SHFT)

// Dropped packet re-injection control SCP command
#define CMD_DPRI 30

// Dropped packet re-injection internal control commands (arg1 of SCP message)
#define CMD_DPRI_SET_ROUTER_TIMEOUT           0
#define CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT 1
#define CMD_DPRI_SET_PACKET_TYPES             2
#define CMD_DPRI_GET_STATUS                   3
#define CMD_DPRI_RESET_COUNTERS               4
#define CMD_DPRI_EXIT                         5

// Dropped packet re-injection packet type flags (arg2 of SCP message)
#define DPRI_PACKET_TYPE_MC 1
#define DPRI_PACKET_TYPE_PP 2
#define DPRI_PACKET_TYPE_NN 4
#define DPRI_PACKET_TYPE_FR 8

// ------------------------------------------------------------------------


// ------------------------------------------------------------------------
// types
// ------------------------------------------------------------------------

// dumped packet type
typedef struct {
    uint hdr;
    uint key;
    uint pld;
} dumped_packet_t;

// packet queue type
typedef struct {
    uint head;
    uint tail;
    dumped_packet_t queue[PKT_QUEUE_SIZE];
} pkt_queue_t;
// ------------------------------------------------------------------------


// ------------------------------------------------------------------------
// global variables
// ------------------------------------------------------------------------

// The content of the comms controller SAR register
static uint cc_sar;

// dumped packet queue
static pkt_queue_t pkt_queue;

// statistics
static uint n_dropped_packets;
static uint n_missed_dropped_packets;
static uint n_dropped_packet_overflows;
static uint n_reinjected_packets;

// Determine what to reinject
static bool reinject_mc;
static bool reinject_pp;
static bool reinject_nn;
static bool reinject_fr;

static bool run = true;

// VIC
typedef void (*isr_t) ();
volatile isr_t* const vic_vectors  = (isr_t *) (VIC_BASE + 0x100);
volatile uint* const vic_controls = (uint *) (VIC_BASE + 0x200);


// ------------------------------------------------------------------------
// functions
// ------------------------------------------------------------------------
INT_HANDLER timer_callback() {

    // clear interrupt in timer,
    tc[T1_INT_CLR] = 1;

    // check if router not blocked
    if ((rtr[RTR_STATUS] & RTR_BLOCKED_MASK) == 0) {

        // access packet queue with fiq disabled,
        uint cpsr = cpu_fiq_disable();

        // if queue not empty turn on packet bouncing,
        if (pkt_queue.tail != pkt_queue.head) {

            // restore fiq after queue access,
            cpu_int_restore(cpsr);

            // enable comms. cont. interrupt to bounce packets,
            vic[VIC_ENABLE] = 1 << CC_TNF_INT;
        } else {

            // restore fiq after queue access,
            cpu_int_restore(cpsr);
        }
    }

    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

INT_HANDLER ready_to_send_callback() {

    // TODO: may need to deal with packet timestamp.

    // check if router not blocked
    if ((rtr[RTR_STATUS] & RTR_BLOCKED_MASK) == 0) {

        // access packet queue with fiq disabled,
        uint cpsr = cpu_fiq_disable();

        // if queue not empty bounce packet,
        if (pkt_queue.tail != pkt_queue.head) {

            // dequeue packet,
            uint hdr = pkt_queue.queue[pkt_queue.head].hdr;
            uint pld = pkt_queue.queue[pkt_queue.head].pld;
            uint key = pkt_queue.queue[pkt_queue.head].key;

            // update queue pointer,
            pkt_queue.head = (pkt_queue.head + 1) % PKT_QUEUE_SIZE;

            // restore fiq after queue access,
            cpu_int_restore(cpsr);

            // write header and route,
            cc[CC_TCR] = hdr & PKT_CONTROL_MASK;
            cc[CC_SAR] = cc_sar | (hdr & PKT_ROUTE_MASK);

            // maybe write payload,
            if (hdr & PKT_PLD_MASK) {
                cc[CC_TXDATA] = pld;
            }

            // write key to fire packet,
            cc[CC_TXKEY] = key;

            // Add to statistics
            n_reinjected_packets += 1;

        } else {

            // restore fiq after queue access,
            cpu_int_restore(cpsr);

            // and disable comms. cont. interrupts
            vic[VIC_DISABLE] = 1 << CC_TNF_INT;
        }
    } else {

        // disable comms. cont. interrupts
        vic[VIC_DISABLE] = 1 << CC_TNF_INT;
    }

    // and tell VIC we're done
    vic[VIC_VADDR] = (uint) vic;
}

INT_HANDLER dropped_packet_callback() {

    // get packet from router,
    uint hdr = rtr[RTR_DHDR];
    uint pld = rtr[RTR_DDAT];
    uint key = rtr[RTR_DKEY];

    // clear dump status and interrupt in router,
    uint rtr_dstat = rtr[RTR_DSTAT];

    // only reinject if configured
    uint packet_type = (hdr & PKT_TYPE_MASK);
    if (((packet_type == PKT_TYPE_MC) && reinject_mc) ||
            ((packet_type == PKT_TYPE_PP) && reinject_pp) ||
            ((packet_type == PKT_TYPE_NN) && reinject_nn) ||
            ((packet_type == PKT_TYPE_FR) && reinject_fr)) {

        // check for overflow from router
        if (rtr_dstat & RTR_DOVRFLW_MASK) {
            n_missed_dropped_packets += 1;
        }

        // Only update this counter if this is a packet to reinject
        n_dropped_packets += 1;

        // try to insert dumped packet in the queue,
        uint new_tail = (pkt_queue.tail + 1) % PKT_QUEUE_SIZE;

        // check for space in the queue
        if (new_tail != pkt_queue.head) {

            // queue packet,
            pkt_queue.queue[pkt_queue.tail].hdr = hdr;
            pkt_queue.queue[pkt_queue.tail].key = key;
            pkt_queue.queue[pkt_queue.tail].pld = pld;

            // update queue pointer,
            pkt_queue.tail = new_tail;

        } else {

            // The queue of packets has overflowed
            n_dropped_packet_overflows += 1;
        }
    }
}

static uint sark_cmd_dpri(sdp_msg_t *msg) {
    io_printf(IO_BUF, "Received command %u, seq %u\n", msg->arg1, msg->seq);

    if (msg->arg1 == CMD_DPRI_SET_ROUTER_TIMEOUT) {

        // Set the router wait1 timeout
        if (msg->arg2 > 0xFF) {
            msg->cmd_rc = RC_ARG;
            return 0;
        }
        rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0xff00ffff)
            | ((msg->arg2 & 0xFF) << 16);
        return 0;

    } else if (msg->arg1 == CMD_DPRI_SET_ROUTER_EMERGENCY_TIMEOUT) {

        // Set the router wait2 timeout
        if (msg->arg2 > 0xFF) {
            msg->cmd_rc = RC_ARG;
            return 0;
        }
        rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x00ffffff)
            | ((msg->arg2 & 0xFF) << 24);
        return 0;

    } else if (msg->arg1 == CMD_DPRI_SET_PACKET_TYPES) {
        io_printf(IO_BUF, "Setting packet types to 0x%.8x\n", msg->arg2);

        // Set the re-injection options
        reinject_mc = (msg->arg2 & DPRI_PACKET_TYPE_MC) != 0;
        reinject_pp = (msg->arg2 & DPRI_PACKET_TYPE_PP) != 0;
        reinject_nn = (msg->arg2 & DPRI_PACKET_TYPE_NN) != 0;
        reinject_fr = (msg->arg2 & DPRI_PACKET_TYPE_FR) != 0;
        return 0;

    } else if (msg->arg1 == CMD_DPRI_GET_STATUS) {

        // Get the status and put it in the packet
        uint *data = &(msg->arg1);

        // Put the router timeouts in the packet
        uint control = (uint) (rtr[RTR_CONTROL] & 0xFFFF0000);
        data[0] = (control >> 16) & 0xFF;
        data[1] = (control >> 24) & 0xFF;

        // Put the statistics in the packet
        data[2] = n_dropped_packets;
        data[3] = n_missed_dropped_packets;
        data[4] = n_dropped_packet_overflows;
        data[5] = n_reinjected_packets;

        // Put the current services enabled in the packet
        data[6] = 0;
        bool values_to_check[] = {reinject_mc, reinject_pp,
                                  reinject_nn, reinject_fr};
        int flags[] = {DPRI_PACKET_TYPE_MC, DPRI_PACKET_TYPE_PP,
                       DPRI_PACKET_TYPE_NN, DPRI_PACKET_TYPE_FR};
        for (int i = 0; i < 4; i++) {
            if (values_to_check[i]) {
                data[6] |= flags[i];
            }
        }

        // Return the number of bytes in the packet
        return 7 * 4;

    } else if (msg->arg1 == CMD_DPRI_RESET_COUNTERS) {

        // Reset the counters
        n_dropped_packets = 0;
        n_missed_dropped_packets = 0;
        n_dropped_packet_overflows = 0;
        n_reinjected_packets = 0;

        return 0;
    } else if (msg->arg1 == CMD_DPRI_EXIT) {
        uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT);
        vic[VIC_DISABLE] = int_select;
        vic[VIC_DISABLE] = (1 << CC_TNF_INT);
        vic[VIC_SELECT] = 0;
        run = false;

        return 0;
    }

    // If we are here, the command was not recognised, so fail (ARG as the
    // command is an argument)
    msg->cmd_rc = RC_ARG;
    return 0;
}

static uint handle_scp_message(sdp_msg_t *msg) {
    uint len = msg->length;

    if (len < 24) {
        msg->cmd_rc = RC_LEN;
        return 0;
    }

    uint cmd = msg->cmd_rc;
    msg->cmd_rc = RC_OK;

    if (cmd == CMD_DPRI) {
        return sark_cmd_dpri(msg);
    }

    msg->cmd_rc = RC_CMD;
    return 0;
}

void __real_sark_int(void *pc);
void __wrap_sark_int(void *pc) {

    // Check for extra messages added by this core
    uint cmd = sark.vcpu->mbox_ap_cmd;
    if (cmd == SHM_MSG) {

        sc[SC_CLR_IRQ] = SC_CODE + (1 << sark.phys_cpu);
        sdp_msg_t *shm_msg = (sdp_msg_t *) sark.vcpu->mbox_ap_msg;
        sdp_msg_t *msg = sark_msg_get();

        if (msg != NULL) {
            sark_msg_cpy(msg, shm_msg);
            sark_shmsg_free(shm_msg);

            uint dp = msg->dest_port;

            if ((dp & PORT_MASK) == 0) {
                msg->length = 12 + handle_scp_message(msg);
                uint dest_port = msg->dest_port;
                uint dest_addr = msg->dest_addr;

                msg->dest_port = msg->srce_port;
                msg->srce_port = dest_port;

                msg->dest_addr = msg->srce_addr;
                msg->srce_addr = dest_addr;

                sark_msg_send(msg, 10);
                sark_msg_free(msg);
            } else {
                sark_msg_free(msg);
            }
        } else {
            sark_shmsg_free(shm_msg);
            sark_msg_free(msg);
        }
    } else {

        // Run the default callback
        __real_sark_int(pc);
    }
}

void configure_timer() {

    // Clear the interrupt
    tc[T1_CONTROL] = 0;
    tc[T1_INT_CLR] = 1;

    // Set the timer times
    tc[T1_LOAD] = sv->cpu_clk * TICK_PERIOD;
    tc[T1_BG_LOAD] = sv->cpu_clk * TICK_PERIOD;
}

void configure_comms_controller() {

    // remember SAR register contents (p2p source ID)
    cc_sar = cc[CC_SAR] & 0x0000ffff;
}

void configure_router() {

    // re-configure wait values in router
    rtr[RTR_CONTROL] = (rtr[RTR_CONTROL] & 0x0000ffff) | ROUTER_INITIAL_TIMEOUT;

    // clear router interrupts,
    (void) rtr[RTR_STATUS];

    // clear router dump status,
    (void) rtr[RTR_DSTAT];

    // and enable router interrupts when dumping packets
    rtr[RTR_CONTROL] |= RTR_DENABLE_MASK;
}

void c_main() {
    sark_cpu_state(CPU_STATE_RUN);

    // Configure
    configure_timer();
    configure_comms_controller();
    configure_router();

    // Initialise the statistics
    n_dropped_packets = 0;
    n_reinjected_packets = 0;
    n_missed_dropped_packets = 0;
    n_dropped_packet_overflows = 0;

    // Initially, only reinject mc
    reinject_mc = true;
    reinject_pp = false;
    reinject_nn = false;
    reinject_fr = false;

    // Disable the interrupts that we are configuring (except CPU for watchdog)
    uint int_select = (1 << TIMER1_INT) | (1 << RTR_DUMP_INT);
    vic[VIC_DISABLE] = int_select;
    vic[VIC_DISABLE] = (1 << CC_TNF_INT);

    // Setup the CPU interrupt for watchdog
    vic_controls[sark_vec->sark_slot] = 0;
    vic_vectors[CPU_SLOT]  = sark_int_han;
    vic_controls[CPU_SLOT] = 0x20 | CPU_INT;

    // Setup the comms controller interrupt
    vic_vectors[CC_SLOT]  = ready_to_send_callback;
    vic_controls[CC_SLOT] = 0x20 | CC_TNF_INT;

    // Setup the timer interrupt
    vic_vectors[TIMER_SLOT]  = timer_callback;
    vic_controls[TIMER_SLOT] = 0x20 | TIMER1_INT;

    // Setup the router interrupt as a fast interrupt
    sark_vec->fiq_vec = dropped_packet_callback;
    vic[VIC_SELECT] = 1 << RTR_DUMP_INT;

    // Enable interrupts and timer
    vic[VIC_ENABLE] = int_select;
    tc[T1_CONTROL] = 0xe2;

    // Run until told to exit
    while (run) {
        spin1_wfi();
    }
}
// ------------------------------------------------------------------------
